"""Unit tests for incremental inbox filtering (no Gmail API)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.services.inbox_processing import (
    filter_inbox_for_processing,
    scan_inbox_for_actionable,
)

CONFIG = {
    "labels": {
        "Newsletters": "Content/Newsletters",
        "Finance": "Finance",
    },
    "processing": {
        "deduplicate": True,
        "target_unprocessed_per_cycle": 2,
        "gmail_page_size": 2,
        "max_scan_pages": 5,
    },
    "app": {"gmail_query": "newer_than:14d"},
}


class MockGmail:
    def __init__(self, label_map: dict) -> None:
        self._id_to_name = {v: k for k, v in label_map.items()}

    def ensure_managed_label_maps(self, names, force_refresh=False):
        return {n: f"id_{n}" for n in names if n in self._id_to_name.values() or True}

    def find_managed_label_on_message(self, label_ids):
        for lid in label_ids or []:
            if lid in self._id_to_name:
                return self._id_to_name[lid], lid
        return None


class InboxProcessingTests(unittest.TestCase):
    def test_label_skip_before_dedup(self) -> None:
        gmail = MockGmail({"Content/Newsletters": "Label_NL"})
        gmail._id_to_name = {"Label_NL": "Content/Newsletters"}
        gmail.ensure_managed_label_maps = lambda *a, **k: None

        store = MagicMock()
        store.has_been_processed.return_value = False

        fetched = [
            {"id": "1", "labelIds": ["Label_NL"], "sender": "a", "subject": "s"},
            {"id": "2", "labelIds": ["INBOX"], "sender": "b", "subject": "t"},
        ]
        result = filter_inbox_for_processing(
            fetched,
            gmail=gmail,
            config=CONFIG,
            store=store,
            force_reprocess=False,
        )
        self.assertEqual(len(result.label_skipped), 1)
        self.assertEqual(result.label_skipped[0]["message_id"], "1")
        self.assertEqual(result.label_skipped[0]["matched_label_id"], "Label_NL")
        self.assertEqual(len(result.to_process), 1)
        self.assertEqual(result.to_process[0]["id"], "2")
        store.has_been_processed.assert_called_once_with("2")

    def test_dedup_skip_when_unlabelled(self) -> None:
        gmail = MockGmail({})
        gmail._id_to_name = {}
        gmail.ensure_managed_label_maps = lambda *a, **k: None
        gmail.find_managed_label_on_message = lambda ids: None

        store = MagicMock()
        store.has_been_processed.return_value = True

        fetched = [{"id": "x", "labelIds": ["INBOX"]}]
        result = filter_inbox_for_processing(
            fetched,
            gmail=gmail,
            config=CONFIG,
            store=store,
        )
        self.assertEqual(len(result.dedup_skipped), 1)
        self.assertEqual(len(result.to_process), 0)

    def test_paginated_scan_continues_past_labelled_page(self) -> None:
        """When page 1 is all label-skipped, scan page 2 for actionable mail."""
        gmail = MagicMock()
        gmail.ensure_managed_label_maps.return_value = {}
        pages = [
            (["a1", "a2"], "page2"),
            (["b1"], None),
        ]
        call_idx = {"n": 0}

        def list_page(*, query=None, max_results=25, page_token=None):
            idx = call_idx["n"]
            call_idx["n"] += 1
            return pages[idx]

        gmail.list_message_ids_page.side_effect = list_page

        from backend.infrastructure.gmail.gmail_transport import FetchBatchResult

        def fetch_ids(ids, page=0):
            out = []
            for mid in ids:
                if mid.startswith("a"):
                    out.append(
                        {"id": mid, "labelIds": ["Label_NL"], "sender": "x", "subject": "s"}
                    )
                else:
                    out.append({"id": mid, "labelIds": ["INBOX"], "sender": "y", "subject": "t"})
            return FetchBatchResult(
                emails=out,
                failed_ids=[],
                requested=len(ids),
                succeeded=len(out),
                failed=0,
                elapsed_ms=1.0,
            )

        gmail.fetch_messages_by_ids.side_effect = fetch_ids
        gmail.find_managed_label_on_message.side_effect = (
            lambda lids: ("Content/Newsletters", "Label_NL")
            if "Label_NL" in (lids or [])
            else None
        )

        store = MagicMock()
        store.has_been_processed.return_value = False

        scan = scan_inbox_for_actionable(
            gmail,
            config=CONFIG,
            store=store,
            target_unprocessed=2,
        )
        self.assertEqual(scan.pages_scanned, 2)
        self.assertEqual(scan.fetched_total, 3)
        self.assertEqual(len(scan.filter_result.label_skipped), 2)
        self.assertEqual(len(scan.filter_result.to_process), 1)
        self.assertEqual(scan.filter_result.to_process[0]["id"], "b1")


if __name__ == "__main__":
    unittest.main()
