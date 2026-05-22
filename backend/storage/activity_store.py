"""
Persistent log of recent classification events for dashboard / review queue.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.paths import BACKEND_DATA_DIR

DATA_DIR = BACKEND_DATA_DIR
DB_PATH = DATA_DIR / "activity.db"
DATA_DIR.mkdir(exist_ok=True)


class ActivityStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS classification_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                sender TEXT,
                subject TEXT,
                snippet TEXT,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT,
                action_applied INTEGER DEFAULT 0,
                score_margin INTEGER,
                top_score INTEGER,
                second_category TEXT,
                review_reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_activity_created
            ON classification_activity(created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_activity_review
            ON classification_activity(review_reason)
            """
        )
        self.conn.commit()

    def record(
        self,
        *,
        message_id: Optional[str],
        sender: str,
        subject: str,
        snippet: str,
        category: str,
        confidence: float,
        source: str,
        action_applied: bool,
        score_margin: Optional[int] = None,
        top_score: Optional[int] = None,
        second_category: Optional[str] = None,
        review_reason: Optional[str] = None,
    ) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO classification_activity (
                message_id, sender, subject, snippet, category, confidence,
                source, action_applied, score_margin, top_score,
                second_category, review_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                sender[:500] if sender else "",
                subject[:500] if subject else "",
                (snippet or "")[:500],
                category,
                float(confidence),
                source or "rules",
                1 if action_applied else 0,
                score_margin,
                top_score,
                second_category,
                review_reason,
                ts,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT message_id, sender, subject, snippet, category, confidence,
                   source, action_applied, score_margin, top_score,
                   second_category, review_reason, created_at
            FROM classification_activity
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def list_review_candidates(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT message_id, sender, subject, snippet, category, confidence,
                   source, action_applied, score_margin, top_score,
                   second_category, review_reason, created_at
            FROM classification_activity
            WHERE review_reason IS NOT NULL AND review_reason != ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def list_low_confidence(self, threshold: float, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT message_id, sender, subject, snippet, category, confidence,
                   source, action_applied, score_margin, top_score,
                   second_category, review_reason, created_at
            FROM classification_activity
            WHERE confidence < ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (threshold, limit),
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def count_total(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM classification_activity")
        return int(cur.fetchone()[0])

    def category_totals(self) -> Dict[str, int]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT category, COUNT(*) FROM classification_activity
            GROUP BY category ORDER BY COUNT(*) DESC
            """
        )
        return {row[0]: int(row[1]) for row in cur.fetchall()}

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        return {
            "message_id": row[0],
            "sender": row[1],
            "subject": row[2],
            "snippet": row[3],
            "category": row[4],
            "confidence": float(row[5]),
            "source": row[6],
            "action_applied": bool(row[7]),
            "score_margin": row[8],
            "top_score": row[9],
            "second_category": row[10],
            "review_reason": row[11],
            "created_at": row[12],
        }


activity_store = ActivityStore()
