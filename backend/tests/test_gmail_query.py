"""Unit tests for Gmail query resolution (no API calls)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config import DEFAULT_GMAIL_QUERY, resolve_gmail_query


class GmailQueryResolutionTests(unittest.TestCase):
    def test_request_override(self) -> None:
        q = resolve_gmail_query("newer_than:3d", {"app": {"gmail_query": "newer_than:14d"}})
        self.assertEqual(q, "newer_than:3d")

    def test_config_fallback(self) -> None:
        q = resolve_gmail_query(None, {"app": {"gmail_query": "newer_than:7d"}})
        self.assertEqual(q, "newer_than:7d")

    def test_empty_request_uses_config(self) -> None:
        q = resolve_gmail_query("", {"app": {"gmail_query": "newer_than:7d"}})
        self.assertEqual(q, "newer_than:7d")

    def test_empty_config_uses_default(self) -> None:
        q = resolve_gmail_query(None, {"app": {"gmail_query": ""}})
        self.assertEqual(q, DEFAULT_GMAIL_QUERY)

    def test_all_empty_uses_default(self) -> None:
        q = resolve_gmail_query("", {"app": {}})
        self.assertEqual(q, DEFAULT_GMAIL_QUERY)

    def test_swagger_placeholder_string_uses_config(self) -> None:
        q = resolve_gmail_query(
            "string",
            {"app": {"gmail_query": "newer_than:14d -in:sent -in:chats"}},
        )
        self.assertEqual(q, "newer_than:14d -in:sent -in:chats")


if __name__ == "__main__":
    unittest.main()
