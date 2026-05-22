"""
Tests for dashboard / review / score margin helpers (no Gmail).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.storage.activity_store import ActivityStore
from backend.rules.score_margin import (
    compute_score_margin_for_email,
    review_reason_from_signals,
)


class ScoreMarginTests(unittest.TestCase):
    def test_margin_for_newsletter(self) -> None:
        m = compute_score_margin_for_email(
            "TLDR <hello@tldrnewsletter.com>",
            "TLDR Daily — tech roundup",
            "Weekly digest",
        )
        self.assertGreaterEqual(m["top_score"], 5)
        self.assertIn("score_margin", m)

    def test_review_reason_low_confidence(self) -> None:
        reason = review_reason_from_signals(
            confidence=0.55,
            source="rules",
            score_margin=8,
        )
        self.assertEqual(reason, "low_confidence")

    def test_review_reason_semantic(self) -> None:
        reason = review_reason_from_signals(
            confidence=0.85,
            source="semantic",
            score_margin=8,
        )
        self.assertEqual(reason, "semantic_fallback")


class ActivityStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = ActivityStore(db_path=Path(self._tmp.name) / "act.db")

    def tearDown(self) -> None:
        self.store.conn.close()
        self._tmp.cleanup()

    def test_review_candidates_query(self) -> None:
        self.store.record(
            message_id="m1",
            sender="test@example.com",
            subject="Sale 50% off",
            snippet="",
            category="Promotions",
            confidence=0.62,
            source="semantic",
            action_applied=False,
            score_margin=1,
            top_score=6,
            second_category="Finance",
            review_reason="semantic_fallback",
        )
        rows = self.store.list_review_candidates(10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review_reason"], "semantic_fallback")


if __name__ == "__main__":
    unittest.main()
