"""
Tests for corrections store and sender override threshold.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.storage.corrections_store import (
    MIN_SENDER_OVERRIDE_COUNT,
    CorrectionsStore,
    normalize_sender_key,
)


class CorrectionsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = CorrectionsStore(
            db_path=Path(self._tmp.name) / "test_corrections.db"
        )

    def tearDown(self) -> None:
        self.store.conn.close()
        self._tmp.cleanup()

    def test_normalize_sender_key(self) -> None:
        key = normalize_sender_key(
            "DeepLearning.AI <newsletter@deeplearning.ai>"
        )
        self.assertEqual(key, "newsletter@deeplearning.ai")

    def test_sender_override_after_threshold(self) -> None:
        sender = "newsletter@deeplearning.ai"
        for _ in range(MIN_SENDER_OVERRIDE_COUNT):
            self.store.add_correction(
                message_id=None,
                sender=sender,
                corrected_category="Newsletters",
                previous_category="Finance",
            )
        override = self.store.get_sender_override(sender)
        self.assertIsNotNone(override)
        self.assertEqual(override["category"], "Newsletters")
        self.assertGreaterEqual(override["count"], MIN_SENDER_OVERRIDE_COUNT)

    def test_confusion_from_corrections(self) -> None:
        self.store.add_correction(
            message_id="m1",
            sender="hello@tldrnewsletter.com",
            corrected_category="Newsletters",
            previous_category="Promotions",
        )
        conf = self.store.confusion_from_corrections()
        self.assertEqual(conf.get("Promotions -> Newsletters"), 1)


if __name__ == "__main__":
    unittest.main()
