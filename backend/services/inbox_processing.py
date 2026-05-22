"""
Incremental inbox filtering — Gmail labels are primary state, SQLite dedup is secondary.

Paginated scan: walk Gmail pages until enough actionable mail is collected or limits hit.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.config import resolve_gmail_query
from backend.infrastructure.gmail.gmail_client import GmailClient
from backend.infrastructure.gmail.labels import managed_label_names_from_config
from backend.storage.processed_store import ProcessedEmailStore

_log = logging.getLogger(__name__)


@dataclass
class InboxFilterResult:
    """Outcome of pre-classification inbox filtering."""

    to_process: List[Dict[str, Any]] = field(default_factory=list)
    label_skipped: List[Dict[str, Any]] = field(default_factory=list)
    dedup_skipped: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def fetched_count(self) -> int:
        return len(self.to_process) + len(self.label_skipped) + len(self.dedup_skipped)


@dataclass
class InboxScanResult:
    """Paginated Gmail scan outcome."""

    filter_result: InboxFilterResult = field(default_factory=InboxFilterResult)
    pages_scanned: int = 0
    fetched_total: int = 0
    status_messages: List[str] = field(default_factory=list)
    gmail_list_ms: float = 0.0
    gmail_fetch_messages_ms: float = 0.0
    gmail_fetch_labels_ms: float = 0.0
    filtering_ms: float = 0.0
    gmail_api_ms: float = 0.0
    partial_fetch_failures: int = 0

    @property
    def actionable_found(self) -> int:
        return len(self.filter_result.to_process)


def get_processing_limits(config: Dict[str, Any]) -> Dict[str, int]:
    proc = config.get("processing") or {}
    return {
        "target_unprocessed_per_cycle": int(
            proc.get("target_unprocessed_per_cycle", 25)
        ),
        "gmail_page_size": int(proc.get("gmail_page_size", 25)),
        "max_scan_pages": int(proc.get("max_scan_pages", 10)),
    }


def filter_inbox_for_processing(
    fetched: List[Dict[str, Any]],
    *,
    gmail: GmailClient,
    config: Dict[str, Any],
    store: Optional[ProcessedEmailStore] = None,
    force_reprocess: bool = False,
    managed_map: Optional[Dict[str, str]] = None,
) -> InboxFilterResult:
    """
    Filter fetched messages before classification.

    Gmail managed labels are checked first (primary state).
    SQLite dedup is second (safety / audit).
    """
    result = InboxFilterResult()
    processing_cfg = config.get("processing", {}) or {}
    deduplicate = bool(processing_cfg.get("deduplicate", True))
    managed_names = managed_label_names_from_config(config)

    if managed_map is None:
        managed_map = gmail.ensure_managed_label_maps(managed_names, force_refresh=False)

    label_debug = os.environ.get("LABEL_DEBUG", "").strip() == "1"

    for email in fetched:
        mid = str(email.get("id") or "")
        if not mid:
            continue

        msg_label_ids = email.get("labelIds") or []
        if label_debug:
            _log.debug(
                "[LABEL DEBUG] message_id=%s label_ids=%s",
                mid,
                msg_label_ids,
            )

        matched = gmail.find_managed_label_on_message(msg_label_ids)
        if matched:
            matched_name, matched_id = matched
            if label_debug:
                _log.debug(
                    "[LABEL SKIP] message_id=%s label=%s id=%s",
                    mid,
                    matched_name,
                    matched_id,
                )
            _log.info(
                "[LABEL SKIP] message_id=%s matched_label_name=%s matched_label_id=%s",
                mid,
                matched_name,
                matched_id,
            )
            result.label_skipped.append(
                {
                    "message_id": mid,
                    "sender": email.get("sender"),
                    "subject": email.get("subject"),
                    "skipped_reason": "already_labelled",
                    "matched_label": matched_name,
                    "matched_label_id": matched_id,
                }
            )
            continue

        if deduplicate and not force_reprocess and store is not None:
            if store.has_been_processed(mid):
                _log.info("[DEDUP SKIP] message_id=%s", mid)
                result.dedup_skipped.append(
                    {
                        "message_id": mid,
                        "skipped_reason": "already_processed",
                    }
                )
                continue

        result.to_process.append(email)

    if result.to_process:
        _log.info("[CLASSIFY] count=%d", len(result.to_process))

    return result


def scan_inbox_for_actionable(
    gmail: GmailClient,
    *,
    config: Dict[str, Any],
    query: Optional[str] = None,
    store: Optional[ProcessedEmailStore] = None,
    force_reprocess: bool = False,
    target_unprocessed: Optional[int] = None,
    on_page: Optional[Callable[..., None]] = None,
) -> InboxScanResult:
    """
    Paginated newest-first scan until ``target_unprocessed`` actionable emails
    are collected or ``max_scan_pages`` is reached.
    """
    limits = get_processing_limits(config)
    target = target_unprocessed if target_unprocessed is not None else limits[
        "target_unprocessed_per_cycle"
    ]
    page_size = limits["gmail_page_size"]
    max_pages = limits["max_scan_pages"]

    gmail_query = resolve_gmail_query(query, config)
    _log.info(
        "[GMAIL SCAN] query=%s target=%d page_size=%d max_pages=%d",
        gmail_query,
        target,
        page_size,
        max_pages,
    )

    status: List[str] = ["Scanning inbox..."]
    accumulated = InboxFilterResult()
    pages_scanned = 0
    fetched_total = 0
    page_token: Optional[str] = None
    gmail_list_ms = 0.0
    gmail_fetch_messages_ms = 0.0
    filtering_ms = 0.0
    partial_failures_total = 0

    managed_names = managed_label_names_from_config(config)
    t_labels = time.perf_counter()
    managed_map = gmail.ensure_managed_label_maps(managed_names, force_refresh=False)
    gmail_fetch_labels_ms = (time.perf_counter() - t_labels) * 1000

    while len(accumulated.to_process) < target and pages_scanned < max_pages:
        t_list = time.perf_counter()
        message_ids, page_token = gmail.list_message_ids_page(
            query=gmail_query,
            max_results=page_size,
            page_token=page_token,
        )
        gmail_list_ms += (time.perf_counter() - t_list) * 1000
        if not message_ids:
            _log.info("[GMAIL SCAN] no more messages on page %d", pages_scanned + 1)
            break

        t_fetch = time.perf_counter()
        batch = gmail.fetch_messages_by_ids(message_ids, page=pages_scanned + 1)
        gmail_fetch_messages_ms += (time.perf_counter() - t_fetch) * 1000
        emails = batch.emails
        partial_failures_total += batch.failed

        pages_scanned += 1
        fetched_total += len(message_ids)

        t_filter = time.perf_counter()
        page_result = filter_inbox_for_processing(
            emails,
            gmail=gmail,
            config=config,
            store=store,
            force_reprocess=force_reprocess,
            managed_map=managed_map,
        )
        filtering_ms += (time.perf_counter() - t_filter) * 1000

        accumulated.label_skipped.extend(page_result.label_skipped)
        accumulated.dedup_skipped.extend(page_result.dedup_skipped)

        remaining = target - len(accumulated.to_process)
        if remaining > 0:
            accumulated.to_process.extend(page_result.to_process[:remaining])

        if on_page is not None:
            on_page(
                pages_scanned=pages_scanned,
                fetched_total=fetched_total,
                label_skipped=len(accumulated.label_skipped),
                dedup_skipped=len(accumulated.dedup_skipped),
                classified=len(accumulated.to_process),
                partial_fetch_failures=partial_failures_total,
            )

        _log.info(
            "[GMAIL SCAN] page=%d ids=%d actionable_total=%d label_skip=%d dedup_skip=%d",
            pages_scanned,
            len(message_ids),
            len(accumulated.to_process),
            len(accumulated.label_skipped),
            len(accumulated.dedup_skipped),
        )

        if len(accumulated.to_process) >= target:
            break
        if not page_token:
            break

    if accumulated.label_skipped or accumulated.dedup_skipped:
        status.append("Skipping already-labelled emails...")
    status.append(
        f"Found {len(accumulated.to_process)} new actionable emails..."
    )

    gmail_api_ms = gmail_list_ms + gmail_fetch_messages_ms + gmail_fetch_labels_ms
    _log.info(
        "[GMAIL SCAN TIMING] labels=%.0fms list=%.0fms fetch=%.0fms filter=%.0fms",
        gmail_fetch_labels_ms,
        gmail_list_ms,
        gmail_fetch_messages_ms,
        filtering_ms,
    )

    return InboxScanResult(
        filter_result=accumulated,
        pages_scanned=pages_scanned,
        fetched_total=fetched_total,
        status_messages=status,
        gmail_list_ms=round(gmail_list_ms, 1),
        gmail_fetch_messages_ms=round(gmail_fetch_messages_ms, 1),
        gmail_fetch_labels_ms=round(gmail_fetch_labels_ms, 1),
        filtering_ms=round(filtering_ms, 1),
        gmail_api_ms=round(gmail_api_ms, 1),
        partial_fetch_failures=partial_failures_total,
    )


def count_inference_sources(classifications: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Return (semantic_used, groq_used) from classifier result dicts."""
    from backend.infrastructure.llm.rule_trust import normalize_classification_path

    semantic = 0
    groq = 0
    for c in classifications:
        path = normalize_classification_path(c.get("source") or "rules")
        if path in ("rules_verified", "semantic_fallback"):
            semantic += 1
        elif path == "groq_escalation":
            groq += 1
    return semantic, groq


def build_processing_metrics(
    *,
    scan: Optional[InboxScanResult] = None,
    fetched: Optional[int] = None,
    filter_result: Optional[InboxFilterResult] = None,
    classifications: Optional[List[Dict[str, Any]]] = None,
    actions_applied: int = 0,
) -> Dict[str, int]:
    """Operational metrics for API responses."""
    if scan is not None:
        filter_result = scan.filter_result
        fetched_total = scan.fetched_total
        pages_scanned = scan.pages_scanned
    else:
        filter_result = filter_result or InboxFilterResult()
        fetched_total = fetched or filter_result.fetched_count
        pages_scanned = 0

    classified = len(filter_result.to_process)
    semantic_used, groq_used = (
        count_inference_sources(classifications) if classifications else (0, 0)
    )
    partial_fetch_failures = 0
    if scan is not None:
        partial_fetch_failures = int(getattr(scan, "partial_fetch_failures", 0) or 0)

    return {
        "pages_scanned": pages_scanned,
        "fetched_total": fetched_total,
        "fetched": fetched_total,
        "label_skipped": len(filter_result.label_skipped),
        "dedup_skipped": len(filter_result.dedup_skipped),
        "actionable_found": classified,
        "classified": classified,
        "semantic_used": semantic_used,
        "groq_used": groq_used,
        "actions_applied": actions_applied,
        "partial_fetch_failures": partial_fetch_failures,
    }
