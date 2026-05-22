import logging
import os
import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build

from backend.config import resolve_gmail_query
from backend.infrastructure.gmail.gmail_transport import (
    FetchBatchResult,
    SSL_STORM_THRESHOLD,
    TransportErrorKind,
    backoff_seconds,
    classify_transport_error,
    clamp_fetch_concurrency,
    log_retry,
    max_retries_for_kind,
    transport_metrics,
)

from backend.paths import BACKEND_DIR

CREDENTIALS_PATH = BACKEND_DIR / "credentials.json"
TOKEN_PATH = BACKEND_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

_MESSAGE_METADATA_FIELDS = (
    "id,threadId,snippet,labelIds,payload(headers)"
)
_METADATA_HEADERS = ["From", "Subject"]


def _gmail_http_settings() -> Dict[str, int]:
    try:
        from backend.config import load_config

        gmail_cfg = load_config().get("gmail") or {}
        return {
            "timeout": int(gmail_cfg.get("http_timeout_seconds", 120)),
            "fetch_concurrency": clamp_fetch_concurrency(
                int(gmail_cfg.get("fetch_concurrency", 3))
            ),
        }
    except Exception:
        return {"timeout": 120, "fetch_concurrency": 3}


class GmailClient:

    def __init__(self):

        settings = _gmail_http_settings()
        self._http_timeout = settings["timeout"]
        self._fetch_concurrency = settings["fetch_concurrency"]
        self._api_lock = threading.Lock()
        self.service = self.authenticate()
        self._managed_name_to_id: Dict[str, str] = {}
        self._managed_id_to_name: Dict[str, str] = {}
        self._all_labels_cache: Dict[str, str] = {}
        self._labels_fetched_at: float = 0.0

    def _execute(
        self,
        request: Any,
        *,
        message_id: Optional[str] = None,
    ) -> Any:
        """Serialized Gmail HTTP execute with typed retries and backoff."""
        last_exc: Optional[BaseException] = None
        kind = TransportErrorKind.OTHER
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                with self._api_lock:
                    return request.execute()
            except Exception as exc:
                last_exc = exc
                kind = classify_transport_error(exc)
                max_attempts = max_retries_for_kind(kind)
                if attempt >= max_attempts:
                    break
                transport_metrics.record_retry(kind)
                delay = backoff_seconds(attempt, kind)
                log_retry(
                    attempt=attempt,
                    max_attempts=max_attempts,
                    kind=kind,
                    delay=delay,
                    message_id=message_id,
                    exc=exc,
                )
                time.sleep(delay)

        assert last_exc is not None
        raise last_exc

    def authenticate(self):

        creds = None

        if TOKEN_PATH.exists():

            creds = Credentials.from_authorized_user_file(
                str(TOKEN_PATH),
                SCOPES
            )

        if not creds or not creds.valid:

            if creds and creds.expired and creds.refresh_token:

                creds.refresh(Request())

            else:

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH),
                    SCOPES
                )

                creds = flow.run_local_server(port=0)

            with open(TOKEN_PATH, "w") as token:

                token.write(creds.to_json())

        timeout = int(os.environ.get("GMAIL_HTTP_TIMEOUT_SECONDS", self._http_timeout))
        http = httplib2.Http(timeout=timeout)
        authorized_http = AuthorizedHttp(creds, http=http)

        service = build(
            "gmail",
            "v1",
            http=authorized_http,
            cache_discovery=False,
        )

        return service

    def list_message_ids_page(
        self,
        *,
        query: Optional[str] = None,
        max_results: int = 25,
        page_token: Optional[str] = None,
    ) -> tuple[List[str], Optional[str]]:
        gmail_query = resolve_gmail_query(query)
        kwargs: Dict = {
            "userId": "me",
            "q": gmail_query,
            "maxResults": max_results,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        response = self._execute(self.service.users().messages().list(**kwargs))
        messages = response.get("messages") or []
        ids = [str(m["id"]) for m in messages if m.get("id")]
        next_token = response.get("nextPageToken")
        return ids, next_token

    def _fetch_one_metadata(self, msg_id: str) -> Dict:
        full_msg = self._execute(
            self.service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=_METADATA_HEADERS,
                fields=_MESSAGE_METADATA_FIELDS,
            ),
            message_id=msg_id,
        )
        return self.parse_message_metadata(full_msg)

    def fetch_messages_by_ids(
        self,
        message_ids: List[str],
        *,
        page: int = 0,
    ) -> FetchBatchResult:
        """Low-concurrency metadata fetch; serializes HTTP via lock for SSL stability."""
        if not message_ids:
            return FetchBatchResult([], [], 0, 0, 0, 0.0)

        t0 = time.perf_counter()
        workers = min(self._fetch_concurrency, len(message_ids))
        by_id: Dict[str, Dict] = {}
        failed_ids: List[str] = []
        ssl_errors_in_batch = 0
        aborted_early = False

        def _worker(mid: str) -> Tuple[str, Optional[Dict], Optional[BaseException]]:
            try:
                return mid, self._fetch_one_metadata(mid), None
            except Exception as exc:
                return mid, None, exc

        # Sequential path when concurrency is 1 (most stable on Windows SSL).
        if workers <= 1:
            for mid in message_ids:
                mid_r, email, exc = _worker(mid)
                if exc is not None:
                    failed_ids.append(mid_r)
                    if classify_transport_error(exc) == TransportErrorKind.SSL:
                        ssl_errors_in_batch += 1
                elif email:
                    by_id[mid_r] = email
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_worker, mid): mid for mid in message_ids}
                for fut in as_completed(futures):
                    mid, email, exc = fut.result()
                    if exc is not None:
                        failed_ids.append(mid)
                        if classify_transport_error(exc) == TransportErrorKind.SSL:
                            ssl_errors_in_batch += 1
                            if ssl_errors_in_batch >= SSL_STORM_THRESHOLD:
                                aborted_early = True
                                _log.error(
                                    "[GMAIL FETCH] SSL storm detected (%d errors); "
                                    "aborting remaining fetches in this batch",
                                    ssl_errors_in_batch,
                                )
                                for pending in futures:
                                    if not pending.done():
                                        pending.cancel()
                                break
                    elif email:
                        by_id[mid] = email

        emails = [by_id[mid] for mid in message_ids if mid in by_id]
        elapsed_ms = (time.perf_counter() - t0) * 1000
        failed = len(failed_ids)
        succeeded = len(emails)

        if failed:
            transport_metrics.record_partial_failures(failed)

        _log.info(
            "[GMAIL FETCH] page=%s ids_requested=%d success=%d failed=%d "
            "concurrency=%d elapsed_ms=%.0f aborted_early=%s",
            page or "-",
            len(message_ids),
            succeeded,
            failed,
            workers,
            elapsed_ms,
            aborted_early,
        )

        return FetchBatchResult(
            emails=emails,
            failed_ids=failed_ids,
            requested=len(message_ids),
            succeeded=succeeded,
            failed=failed,
            elapsed_ms=elapsed_ms,
            aborted_early=aborted_early,
        )

    def fetch_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 25,
    ) -> List[Dict]:
        gmail_query = resolve_gmail_query(query)
        _log.info("[GMAIL QUERY] %s max_results=%d", gmail_query, max_results)
        ids, _ = self.list_message_ids_page(query=gmail_query, max_results=max_results)
        batch = self.fetch_messages_by_ids(ids)
        return batch.emails

    def get_messages(
        self,
        max_results: int = 25,
        query: Optional[str] = None,
    ) -> List[Dict]:
        return self.fetch_emails(query=query, max_results=max_results)

    @staticmethod
    def parse_message_metadata(message: Dict) -> Dict:
        headers = message.get("payload", {}).get("headers", [])
        header_map = {h["name"]: h["value"] for h in headers if h.get("name")}
        snippet = message.get("snippet", "") or ""
        return {
            "id": message["id"],
            "thread_id": message.get("threadId"),
            "sender": header_map.get("From", ""),
            "subject": header_map.get("Subject", ""),
            "snippet": snippet,
            "body": snippet,
            "labelIds": message.get("labelIds", []),
        }

    def parse_message(self, message: Dict) -> Dict:
        headers = message["payload"].get("headers", [])
        header_map = {h["name"]: h["value"] for h in headers}
        body = self.extract_body(message)
        return {
            "id": message["id"],
            "thread_id": message.get("threadId"),
            "sender": header_map.get("From", ""),
            "subject": header_map.get("Subject", ""),
            "snippet": message.get("snippet", ""),
            "body": body,
            "labelIds": message.get("labelIds", []),
        }

    def extract_body(self, message: Dict) -> str:
        payload = message.get("payload", {})
        parts = payload.get("parts", [])
        body = ""
        if parts:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data")
                    if data:
                        body += base64.urlsafe_b64decode(data).decode(errors="ignore")
        else:
            data = payload.get("body", {}).get("data")
            if data:
                body += base64.urlsafe_b64decode(data).decode(errors="ignore")
        return body

    def get_existing_labels(self, force_refresh: bool = False) -> Dict[str, str]:
        if self._all_labels_cache and not force_refresh:
            return dict(self._all_labels_cache)
        _log.info("[GMAIL] Fetching label list (force_refresh=%s)", force_refresh)
        response = self._execute(
            self.service.users().labels().list(userId="me")
        )
        labels = response.get("labels", [])
        self._all_labels_cache = {label["name"]: label["id"] for label in labels}
        self._labels_fetched_at = time.time()
        _log.info("[GMAIL] Cached %d labels", len(self._all_labels_cache))
        return dict(self._all_labels_cache)

    def register_label_in_cache(self, name: str, label_id: str) -> None:
        self._all_labels_cache[name] = label_id

    def invalidate_label_caches(self) -> None:
        self._managed_name_to_id.clear()
        self._managed_id_to_name.clear()

    def ensure_managed_label_maps(
        self, managed_label_names: List[str], force_refresh: bool = False
    ) -> Dict[str, str]:
        all_labels = self.get_existing_labels(force_refresh=force_refresh)
        name_to_id: Dict[str, str] = {}
        id_to_name: Dict[str, str] = {}
        for name in managed_label_names:
            lid = all_labels.get(name)
            if lid:
                name_to_id[name] = lid
                id_to_name[lid] = name
        self._managed_name_to_id = name_to_id
        self._managed_id_to_name = id_to_name
        return dict(name_to_id)

    def find_managed_label_on_message(
        self, label_ids: Optional[List[str]]
    ) -> Optional[tuple[str, str]]:
        for lid in label_ids or []:
            name = self._managed_id_to_name.get(lid)
            if name:
                return name, lid
        return None

    def create_label(self, label_name: str) -> str:
        existing = self.get_existing_labels()
        if label_name in existing:
            return existing[label_name]

        body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }

        created = self._execute(
            self.service.users().labels().create(userId="me", body=body)
        )
        label_id = created["id"]
        self.register_label_in_cache(label_name, label_id)
        return label_id

    def apply_label(self, message_id: str, label_id: str) -> None:
        self._execute(
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id]},
            ),
            message_id=message_id,
        )

    def batch_modify_messages(
        self,
        message_ids: List[str],
        *,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> int:
        add_label_ids = add_label_ids or []
        remove_label_ids = remove_label_ids or []
        if not message_ids:
            return 0
        chunk_size = 1000
        modified = 0
        for start in range(0, len(message_ids), chunk_size):
            chunk = message_ids[start : start + chunk_size]
            body: Dict[str, Any] = {"ids": chunk}
            if add_label_ids:
                body["addLabelIds"] = add_label_ids
            if remove_label_ids:
                body["removeLabelIds"] = remove_label_ids
            self._execute(
                self.service.users().messages().batchModify(userId="me", body=body)
            )
            modified += len(chunk)
        return modified
