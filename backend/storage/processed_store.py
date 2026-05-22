"""
SQLite-backed deduplication store for Gmail Genie.

Tracks already-processed Gmail message IDs to avoid reprocessing.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


from backend.paths import PROJECT_DATA_DIR

DATA_DIR = PROJECT_DATA_DIR
DB_PATH = DATA_DIR / "cache.db"
DATA_DIR.mkdir(exist_ok=True)


class ProcessedEmailStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_emails (
                message_id TEXT PRIMARY KEY,
                category TEXT,
                confidence REAL,
                processed_at TEXT,
                action_applied INTEGER
            )
            """
        )
        self.conn.commit()

    def has_been_processed(self, message_id: str) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT 1 FROM processed_emails WHERE message_id=? LIMIT 1",
            (message_id,),
        )
        return cur.fetchone() is not None

    def mark_processed(
        self,
        *,
        message_id: str,
        category: str,
        confidence: float,
        action_applied: bool,
        processed_at: Optional[str] = None,
    ) -> None:
        ts = processed_at or datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO processed_emails
                (message_id, category, confidence, processed_at, action_applied)
            VALUES
                (?, ?, ?, ?, ?)
            """,
            (message_id, category, float(confidence), ts, 1 if action_applied else 0),
        )
        self.conn.commit()

    def get_record(self, message_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT message_id, category, confidence, processed_at, action_applied
            FROM processed_emails
            WHERE message_id=?
            """,
            (message_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "message_id": row[0],
            "category": row[1],
            "confidence": row[2],
            "processed_at": row[3],
            "action_applied": bool(row[4]),
        }

