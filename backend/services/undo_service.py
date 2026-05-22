"""
Undo the last applied inbox cycle — remove Genie-added labels only.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from backend.services.actions import GmailActions
from backend.config import load_config
from backend.storage.cycle_undo_store import cycle_undo_store
from backend.infrastructure.gmail.labels import managed_label_names_from_config

_log = logging.getLogger(__name__)


def undo_last_cycle(gmail_client: Any) -> Dict[str, Any]:
    record = cycle_undo_store.get_last_cycle()
    if not record:
        return {"success": False, "error": "No cycle available to undo"}
    if record.get("undone_at"):
        return {"success": False, "error": "Last cycle was already undone"}
    if not record.get("can_undo"):
        return {"success": False, "error": "Nothing to undo"}

    cfg = load_config()
    managed_names: Set[str] = set(managed_label_names_from_config(cfg))
    entries = record.get("entries") or []

    actions = GmailActions(gmail_client=gmail_client, config=cfg, dry_run=False)
    actions.get_existing_labels(force_refresh=True)

    removed_count = 0
    messages_touched = 0
    skipped_labels = 0

    for entry in entries:
        message_id = str(entry.get("message_id") or "")
        if not message_id:
            continue
        label_names = entry.get("labels_added") or entry.get("labels") or []
        remove_ids: List[str] = []
        for name in label_names:
            name = str(name).strip()
            if not name or name not in managed_names:
                skipped_labels += 1
                continue
            try:
                remove_ids.append(actions.get_or_create_label(name))
            except Exception as exc:
                _log.warning("Skip undo label %s: %s", name, exc)
                skipped_labels += 1

        if not remove_ids:
            continue

        if actions.dry_run:
            continue

        actions._batch_modify([message_id], remove_label_ids=remove_ids)
        removed_count += len(remove_ids)
        messages_touched += 1

    cycle_undo_store.mark_undone(record["cycle_id"])

    return {
        "success": True,
        "cycle_id": record["cycle_id"],
        "messages_touched": messages_touched,
        "labels_removed": removed_count,
        "skipped_non_genie_labels": skipped_labels,
        "note": "Inbox preserved — only Genie labels from the last run were removed.",
    }
