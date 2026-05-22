"""
Persist the last non-dry-run cycle's Gmail label additions for one-click undo.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.paths import BACKEND_DATA_DIR

DB_PATH = BACKEND_DATA_DIR / "cycle_undo.db"


class CycleUndoStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS undo_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    started_at TEXT,
                    completed_at TEXT NOT NULL,
                    gmail_query TEXT,
                    dry_run INTEGER NOT NULL DEFAULT 0,
                    undone_at TEXT,
                    entries_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_cycle(
        self,
        *,
        started_at: Optional[str],
        gmail_query: str,
        entries: List[Dict[str, Any]],
    ) -> str:
        """Replace previous undo record with the latest applied cycle."""
        if not entries:
            return ""
        cycle_id = str(uuid.uuid4())
        completed_at = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(entries, ensure_ascii=False)
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM undo_cycles")
                conn.execute(
                    """
                    INSERT INTO undo_cycles (
                        cycle_id, started_at, completed_at, gmail_query,
                        dry_run, undone_at, entries_json
                    ) VALUES (?, ?, ?, ?, 0, NULL, ?)
                    """,
                    (cycle_id, started_at, completed_at, gmail_query, payload),
                )
                conn.commit()
        return cycle_id

    def get_last_cycle(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT cycle_id, started_at, completed_at, gmail_query,
                           dry_run, undone_at, entries_json
                    FROM undo_cycles
                    ORDER BY completed_at DESC
                    LIMIT 1
                    """
                ).fetchone()
        if not row:
            return None
        entries = json.loads(row["entries_json"] or "[]")
        return {
            "cycle_id": row["cycle_id"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "gmail_query": row["gmail_query"],
            "dry_run": bool(row["dry_run"]),
            "undone_at": row["undone_at"],
            "entries": entries,
            "can_undo": row["undone_at"] is None and len(entries) > 0,
        }

    def mark_undone(self, cycle_id: str) -> bool:
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    UPDATE undo_cycles SET undone_at = ?
                    WHERE cycle_id = ? AND undone_at IS NULL
                    """,
                    (ts, cycle_id),
                )
                conn.commit()
                return cur.rowcount > 0


cycle_undo_store = CycleUndoStore()
