"""
SQLite store for user classification corrections and sender-override statistics.

Lightweight feedback loop — no Gmail mutations, no ML retraining.
"""

from __future__ import annotations

import sqlite3
import threading
from collections import Counter
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from backend.paths import BACKEND_DATA_DIR

DATA_DIR = BACKEND_DATA_DIR
DB_PATH = DATA_DIR / "corrections.db"
DATA_DIR.mkdir(exist_ok=True)

MIN_SENDER_OVERRIDE_COUNT = 5
SENDER_OVERRIDE_BOOST = 8

# Categories that must not be learned via sender bias alone (safety / transactional).
SENDER_OVERRIDE_BLOCKED_CATEGORIES = frozenset({"Security Alerts"})


def normalize_sender_key(sender: str) -> str:
    """Stable mailbox key for aggregation (lowercase email address)."""
    _, addr = parseaddr((sender or "").strip())
    addr = (addr or "").strip().lower()
    if "@" in addr:
        return addr
    text = (sender or "").strip().lower()
    if "@" in text:
        return text
    return text[:120]


class CorrectionsStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT,
                    sender TEXT NOT NULL,
                    corrected_category TEXT NOT NULL,
                    previous_category TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_corrections_sender ON user_corrections(sender)"
            )
            self.conn.commit()

    def add_correction(
        self,
        *,
        message_id: Optional[str],
        sender: str,
        corrected_category: str,
        previous_category: Optional[str] = None,
    ) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        sender_key = normalize_sender_key(sender)
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO user_corrections
                    (message_id, sender, corrected_category, previous_category, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    sender_key,
                    corrected_category.strip(),
                    (previous_category or "").strip() or None,
                    ts,
                ),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def get_sender_override(self, sender: str) -> Optional[Dict[str, Any]]:
        """
        Return active override when the same sender was corrected to one category
        at least MIN_SENDER_OVERRIDE_COUNT times (majority wins on ties).
        """
        sender_key = normalize_sender_key(sender)
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT corrected_category, COUNT(*) AS cnt
                FROM user_corrections
                WHERE sender = ?
                GROUP BY corrected_category
                ORDER BY cnt DESC
                """,
                (sender_key,),
            )
            rows = cur.fetchall()
        if not rows:
            return None
        top_cat, top_cnt = rows[0][0], int(rows[0][1])
        if top_cnt < MIN_SENDER_OVERRIDE_COUNT:
            return None
        if top_cat in SENDER_OVERRIDE_BLOCKED_CATEGORIES:
            return None
        if len(rows) > 1 and int(rows[1][1]) == top_cnt:
            return None
        return {
            "sender": sender_key,
            "category": top_cat,
            "count": top_cnt,
            "boost": SENDER_OVERRIDE_BOOST,
        }

    def get_sender_statistics(self) -> Dict[str, Any]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM user_corrections")
            total = int(cur.fetchone()[0])
            cur.execute(
                """
                SELECT sender, corrected_category, COUNT(*) AS cnt
                FROM user_corrections
                GROUP BY sender, corrected_category
                HAVING cnt >= ?
                ORDER BY cnt DESC
                """,
                (MIN_SENDER_OVERRIDE_COUNT,),
            )
            active_overrides = [
                {
                    "sender": row[0],
                    "category": row[1],
                    "count": int(row[2]),
                }
                for row in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT corrected_category, COUNT(*) FROM user_corrections
                GROUP BY corrected_category ORDER BY COUNT(*) DESC LIMIT 10
                """
            )
            by_category = {row[0]: int(row[1]) for row in cur.fetchall()}
        return {
            "total_corrections": total,
            "active_sender_overrides": active_overrides,
            "corrections_by_category": by_category,
        }

    def confusion_from_corrections(self) -> Dict[str, int]:
        """previous_category -> corrected_category from user fixes."""
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT previous_category, corrected_category, COUNT(*) AS cnt
                FROM user_corrections
                WHERE previous_category IS NOT NULL AND previous_category != ''
                GROUP BY previous_category, corrected_category
                """
            )
            out: Dict[str, int] = {}
            for prev, corr, cnt in cur.fetchall():
                key = f"{prev} -> {corr}"
                out[key] = int(cnt)
            return out

    def summary_counts(self) -> Dict[str, Any]:
        stats = self.get_sender_statistics()
        confusions = self.confusion_from_corrections()
        top_confusions = sorted(
            confusions.items(), key=lambda x: x[1], reverse=True
        )[:15]
        return {
            "corrections_count": stats["total_corrections"],
            "most_corrected_categories": stats["corrections_by_category"],
            "sender_override_count": len(stats["active_sender_overrides"]),
            "top_confusions": dict(top_confusions),
        }


corrections_store = CorrectionsStore()
