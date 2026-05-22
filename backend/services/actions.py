"""
Gmail action execution layer for Gmail Genie.

Label management, single-message helpers, and batched ``batchModify`` with
dry-run, safety limits, config-driven label paths, and JSONL logging.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config import load_config
from backend.infrastructure.gmail.gmail_client import GmailClient
from backend.infrastructure.gmail.labels import category_to_gmail_label
from backend.policies import never_trash_categories, processing_limits

logger = logging.getLogger(__name__)

BATCH_CHUNK_SIZE = 1000
SYSTEM_INBOX = "INBOX"
SYSTEM_UNREAD = "UNREAD"
SYSTEM_TRASH = "TRASH"


class GmailActions:
    """Apply configured category actions to Gmail messages."""

    def __init__(
        self,
        gmail_client: GmailClient,
        config: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        self.gmail = gmail_client
        self.service = gmail_client.service
        self.config = config or load_config()
        self.dry_run = dry_run
        self.verbose = verbose
        self._label_cache: Dict[str, str] = {}

        self.action_mappings: Dict[str, Dict[str, Any]] = self.config.get(
            "actions", {}
        )
        self.label_mappings: Dict[str, str] = self.config.get("labels", {}) or {}
        self.confidence_threshold = float(
            self.config.get("app", {}).get("confidence_threshold", 0.70)
        )

        limits = processing_limits(self.config)
        self.safety: Dict[str, Any] = self.config.get("safety", {}) or {}
        self.max_actions_per_run = limits["max_actions_per_run"]
        self.max_trash_per_cycle = limits["max_trash_per_cycle"]
        self.never_trash: List[str] = never_trash_categories(self.config)

        self.logging_cfg: Dict[str, Any] = self.config.get("logging", {}) or {}
        self.logging_enabled = bool(self.logging_cfg.get("enabled", True))
        self.log_path = Path(self.logging_cfg.get("path", "backend/logs/actions.log"))
        self.log_dry_run = bool(self.logging_cfg.get("log_dry_run", True))

    def _log(self, message: str) -> None:
        if self.verbose:
            logger.info(message)

    def _log_action(self, payload: Dict[str, Any]) -> None:
        if not self.logging_enabled:
            return
        if self.dry_run and not self.log_dry_run:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            self._log(f"Failed to write actions log: {exc}")

    def _message_id(self, item: Dict[str, Any]) -> str:
        msg_id = item.get("message_id") or item.get("id")
        if not msg_id:
            raise ValueError("email item missing message_id or id")
        return str(msg_id)

    def get_existing_labels(self, force_refresh: bool = False) -> Dict[str, str]:
        if hasattr(self.gmail, "get_existing_labels"):
            self._label_cache = self.gmail.get_existing_labels(
                force_refresh=force_refresh
            )
            return dict(self._label_cache)
        if self._label_cache and not force_refresh:
            return dict(self._label_cache)
        response = self.service.users().labels().list(userId="me").execute()
        labels = response.get("labels", [])
        self._label_cache = {label["name"]: label["id"] for label in labels}
        return dict(self._label_cache)

    def create_label(self, label_name: str) -> str:
        existing = self.get_existing_labels()
        if label_name in existing:
            return existing[label_name]

        if self.dry_run:
            self._log(f"[DRY RUN] Would create label: {label_name}")
            placeholder = f"dry-run:{label_name}"
            self._label_cache[label_name] = placeholder
            return placeholder

        body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created = (
            self.service.users().labels().create(userId="me", body=body).execute()
        )
        label_id = created["id"]
        self._label_cache[label_name] = label_id
        self._log(f"Created label: {label_name} ({label_id})")
        if hasattr(self.gmail, "register_label_in_cache"):
            self.gmail.register_label_in_cache(label_name, label_id)
        self._label_cache[label_name] = label_id
        return label_id

    def get_or_create_label(self, label_name: str) -> str:
        existing = self.get_existing_labels()
        if label_name in existing:
            return existing[label_name]
        return self.create_label(label_name)

    def resolve_gmail_label(self, category: str) -> str:
        return category_to_gmail_label(category, self.config)

    def apply_label(self, message_id: str, label_name: str) -> None:
        label_id = self.get_or_create_label(label_name)
        self._modify_message(message_id, add_label_ids=[label_id])

    def apply_multiple_labels(self, message_id: str, labels: List[str]) -> None:
        label_ids = [self.get_or_create_label(name) for name in labels]
        self._modify_message(message_id, add_label_ids=label_ids)

    def archive_email(self, message_id: str) -> None:
        """Disabled — inbox must stay intact."""
        return

    def trash_email(self, message_id: str) -> None:
        """Disabled — inbox must stay intact."""
        return

    def mark_as_read(self, message_id: str) -> None:
        self._modify_message(message_id, remove_label_ids=[SYSTEM_UNREAD])

    def _modify_message(
        self,
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> None:
        add_label_ids = add_label_ids or []
        remove_label_ids = remove_label_ids or []
        if not add_label_ids and not remove_label_ids:
            return

        if self.dry_run:
            self._log(
                f"[DRY RUN] modify {message_id} "
                f"add={add_label_ids} remove={remove_label_ids}"
            )
            return

        body: Dict[str, Any] = {"ids": [message_id]}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        self.service.users().messages().batchModify(userId="me", body=body).execute()

    def batch_apply_labels(
        self,
        message_ids: List[str],
        label_names: List[str],
    ) -> int:
        if not message_ids or not label_names:
            return 0
        label_ids = [self.get_or_create_label(name) for name in label_names]
        return self._batch_modify(message_ids, add_label_ids=label_ids)

    def batch_archive(self, message_ids: List[str]) -> int:
        return 0

    def batch_trash(self, message_ids: List[str]) -> int:
        return 0

    def _batch_modify(
        self,
        message_ids: List[str],
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> int:
        add_label_ids = add_label_ids or []
        remove_label_ids = remove_label_ids or []
        if not message_ids:
            return 0

        modified = 0
        for start in range(0, len(message_ids), BATCH_CHUNK_SIZE):
            chunk = message_ids[start : start + BATCH_CHUNK_SIZE]
            if self.dry_run:
                self._log(
                    f"[DRY RUN] batchModify {len(chunk)} messages "
                    f"add={add_label_ids} remove={remove_label_ids}"
                )
                modified += len(chunk)
                continue

            body: Dict[str, Any] = {"ids": chunk}
            if add_label_ids:
                body["addLabelIds"] = add_label_ids
            if remove_label_ids:
                body["removeLabelIds"] = remove_label_ids

            self.service.users().messages().batchModify(
                userId="me", body=body
            ).execute()
            modified += len(chunk)

        return modified

    def _resolve_mapping(self, category: str) -> Optional[Dict[str, Any]]:
        mapping = self.action_mappings.get(category)
        if not mapping:
            return None
        apply_label = mapping.get("apply_label")
        return {
            "apply_label": bool(apply_label),
            "archive": False,
            "trash": False,
            "mark_read": bool(mapping.get("mark_read", False)),
        }

    def _build_plan(
        self,
        message_id: str,
        category: str,
        confidence: float,
    ) -> Optional[Dict[str, Any]]:
        if confidence < self.confidence_threshold:
            return None

        mapping = self._resolve_mapping(category)
        if not mapping:
            return None

        should_apply_label = mapping.get("apply_label")
        add_label_ids: List[str] = []
        remove_label_ids: List[str] = []
        apply_label_names: List[str] = []

        if should_apply_label:
            apply_label_name = self.resolve_gmail_label(category)
            apply_label_names = [apply_label_name]
            add_label_ids.append(self.get_or_create_label(apply_label_name))

        mark_read = bool(mapping["mark_read"])
        trash = False
        if trash and category in self.never_trash:
            trash = False

        if mark_read:
            remove_label_ids.append(SYSTEM_UNREAD)

        if not add_label_ids and not remove_label_ids:
            return None

        return {
            "message_id": message_id,
            "category": category,
            "confidence": confidence,
            "apply_label_names": apply_label_names,
            "archive": False,
            "trash": False,
            "mark_read": mark_read,
            "add_label_ids": add_label_ids,
            "remove_label_ids": remove_label_ids,
        }

    def preview_actions(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        prev = self.dry_run
        self.dry_run = True
        try:
            return self.process_batch_results(emails)
        finally:
            self.dry_run = prev

    def process_email_result(
        self,
        email: Dict[str, Any],
        classification: Dict[str, Any],
    ) -> Dict[str, Any]:
        message_id = self._message_id(email)
        category = classification.get("category", "General")
        confidence = float(classification.get("confidence", 0.0))

        plan = self._build_plan(message_id, category, confidence)
        if not plan:
            return {
                "message_id": message_id,
                "category": category,
                "confidence": confidence,
                "applied": False,
                "reason": "below_threshold_or_no_mapping",
            }

        self._execute_plans([plan])
        return {
            "message_id": message_id,
            "category": category,
            "confidence": confidence,
            "applied": True,
            "dry_run": self.dry_run,
            "apply_label_names": plan["apply_label_names"],
            "labels_applied": plan["apply_label_names"],
            "mark_read": plan["mark_read"],
        }

    def process_batch_results(
        self,
        emails: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self.get_existing_labels(force_refresh=False)
        categories_needed = {
            str(item.get("category", "General")) for item in emails
        }
        for cat in categories_needed:
            if self._resolve_mapping(cat):
                name = self.resolve_gmail_label(cat)
                self.get_or_create_label(name)

        plans: List[Dict[str, Any]] = []
        per_email: List[Dict[str, Any]] = []
        skipped_low_confidence = 0
        skipped_no_mapping = 0
        skipped_protected_category = 0
        skipped_safety_limit = 0

        for item in emails:
            message_id = self._message_id(item)
            category = item.get("category", "General")
            confidence = float(item.get("confidence", 0.0))

            if confidence < self.confidence_threshold:
                skipped_low_confidence += 1
                per_email.append(
                    {
                        "message_id": message_id,
                        "category": category,
                        "confidence": confidence,
                        "applied": False,
                        "skipped_reason": "below_confidence_threshold",
                    }
                )
                continue

            mapping = self._resolve_mapping(category)
            if not mapping:
                skipped_no_mapping += 1
                per_email.append(
                    {
                        "message_id": message_id,
                        "category": category,
                        "confidence": confidence,
                        "applied": False,
                        "skipped_reason": "no_action_mapping",
                    }
                )
                continue

            plan = self._build_plan(message_id, category, confidence)
            if plan:
                plans.append(plan)
            else:
                skipped_protected_category += 1
                per_email.append(
                    {
                        "message_id": message_id,
                        "category": category,
                        "confidence": confidence,
                        "applied": False,
                        "skipped_reason": "protected_category_or_no_effect",
                    }
                )

        plans, limit_skips, skipped_safety_limit = self._apply_cycle_safety_limits(plans)
        for plan in limit_skips:
            per_email.append(
                {
                    "message_id": plan["message_id"],
                    "category": plan["category"],
                    "confidence": plan["confidence"],
                    "applied": False,
                    "skipped_reason": plan.get("_skip_reason", "safety_limit"),
                }
            )

        preview = self._plans_to_preview(plans)
        if not plans:
            return {
                "dry_run": self.dry_run,
                "processed": len(emails),
                "applied": 0,
                "skipped_low_confidence": skipped_low_confidence,
                "skipped_no_mapping": skipped_no_mapping,
                "skipped_protected_category": skipped_protected_category,
                "skipped_safety_limit": skipped_safety_limit,
                "emails": per_email,
                **preview,
            }

        batch_stats = self._execute_plans(plans)
        applied_ids = {plan["message_id"] for plan in plans}

        ts = datetime.now(timezone.utc).isoformat()
        for plan in plans:
            entry = {
                "message_id": plan["message_id"],
                "category": plan["category"],
                "confidence": plan["confidence"],
                "applied": True,
                "dry_run": self.dry_run,
                "labels": plan["apply_label_names"],
                "labels_applied": bool(plan["apply_label_names"]),
                "trashed": False,
                "mark_read": bool(plan["mark_read"]),
            }
            per_email.append(entry)
            self._log_action(
                {
                    "timestamp": ts,
                    "dry_run": self.dry_run,
                    "message_id": entry["message_id"],
                    "category": entry["category"],
                    "confidence": entry["confidence"],
                    "labels": entry["labels"],
                    "trashed": entry["trashed"],
                    "mark_read": entry["mark_read"],
                }
            )

        return {
            "dry_run": self.dry_run,
            "processed": len(emails),
            "applied": len(applied_ids),
            "skipped_low_confidence": skipped_low_confidence,
            "skipped_no_mapping": skipped_no_mapping,
            "skipped_protected_category": skipped_protected_category,
            "skipped_safety_limit": skipped_safety_limit,
            "emails": per_email,
            **preview,
            **batch_stats,
        }

    def _apply_cycle_safety_limits(
        self, plans: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        """Enforce per-cycle action caps (inbox never archived)."""
        denied: List[Dict[str, Any]] = []
        allowed: List[Dict[str, Any]] = []

        for plan in plans:
            skip_reason: Optional[str] = None
            if (
                self.max_actions_per_run >= 0
                and len(allowed) >= self.max_actions_per_run
            ):
                skip_reason = "safety_max_actions_per_run"

            if skip_reason:
                denied.append({**plan, "_skip_reason": skip_reason})
                continue

            allowed.append(plan)

        return allowed, denied, len(denied)

    def _plans_to_preview(self, plans: List[Dict[str, Any]]) -> Dict[str, Any]:
        would_apply_labels: List[Dict[str, Any]] = []
        would_mark_read: List[str] = []

        for plan in plans:
            message_id = plan["message_id"]
            if plan["apply_label_names"]:
                would_apply_labels.append(
                    {
                        "message_id": message_id,
                        "labels": plan["apply_label_names"],
                        "category": plan["category"],
                    }
                )
            if plan["mark_read"]:
                would_mark_read.append(message_id)

        return {
            "would_apply_labels": would_apply_labels,
            "would_mark_read": would_mark_read,
        }

    def _execute_plans(
        self,
        plans: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        groups: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], List[str]] = (
            defaultdict(list)
        )

        for plan in plans:
            add_key = tuple(sorted(set(plan["add_label_ids"])))
            remove_key = tuple(sorted(set(plan["remove_label_ids"])))
            groups[(add_key, remove_key)].append(plan["message_id"])

        total_modified = 0
        batch_calls = 0

        for (add_ids, remove_ids), message_ids in groups.items():
            modified = self._batch_modify(
                message_ids,
                add_label_ids=list(add_ids),
                remove_label_ids=list(remove_ids),
            )
            total_modified += modified
            batch_calls += 1

        return {
            "messages_modified": total_modified,
            "batch_calls": batch_calls,
        }
