"""
Lightweight per-day operational metric snapshots.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.paths import BACKEND_DATA_DIR

DB_PATH = BACKEND_DATA_DIR / "daily_metrics.db"
DB_PATH.parent.mkdir(exist_ok=True)


class DailyMetricsStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_snapshots (
                day TEXT PRIMARY KEY,
                processed INTEGER DEFAULT 0,
                label_skipped INTEGER DEFAULT 0,
                semantic_used INTEGER DEFAULT 0,
                groq_used INTEGER DEFAULT 0,
                corrections INTEGER DEFAULT 0,
                top_categories TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cycle_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                completed_at TEXT NOT NULL,
                dry_run INTEGER DEFAULT 0,
                pages_scanned INTEGER DEFAULT 0,
                fetched_total INTEGER DEFAULT 0,
                label_skipped INTEGER DEFAULT 0,
                dedup_skipped INTEGER DEFAULT 0,
                classified INTEGER DEFAULT 0,
                actions_applied INTEGER DEFAULT 0,
                semantic_used INTEGER DEFAULT 0,
                groq_used INTEGER DEFAULT 0,
                gmail_fetch_ms REAL DEFAULT 0,
                filtering_ms REAL DEFAULT 0,
                classify_ms REAL DEFAULT 0,
                actions_ms REAL DEFAULT 0,
                total_cycle_ms REAL DEFAULT 0,
                status TEXT DEFAULT 'ok'
            )
            """
        )
        self._migrate_cycle_runs(cur)
        self.conn.commit()

    def _migrate_cycle_runs(self, cur) -> None:
        cur.execute("PRAGMA table_info(cycle_runs)")
        cols = {row[1] for row in cur.fetchall()}
        if "semantic_rate" not in cols:
            cur.execute(
                "ALTER TABLE cycle_runs ADD COLUMN semantic_rate REAL DEFAULT 0"
            )
        if "top_categories" not in cols:
            cur.execute(
                "ALTER TABLE cycle_runs ADD COLUMN top_categories TEXT"
            )

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def record_cycle(
        self,
        *,
        processed: int = 0,
        label_skipped: int = 0,
        semantic_used: int = 0,
        groq_used: int = 0,
        corrections: int = 0,
        top_categories: Optional[Dict[str, int]] = None,
        day: Optional[str] = None,
    ) -> None:
        day_key = day or self._today()
        ts = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT processed, label_skipped, semantic_used, groq_used, corrections, top_categories FROM daily_snapshots WHERE day=?",
            (day_key,),
        )
        row = cur.fetchone()
        if row:
            merged_cats = self._merge_category_json(row[5], top_categories)
            cur.execute(
                """
                UPDATE daily_snapshots SET
                    processed = processed + ?,
                    label_skipped = label_skipped + ?,
                    semantic_used = semantic_used + ?,
                    groq_used = groq_used + ?,
                    corrections = corrections + ?,
                    top_categories = ?,
                    updated_at = ?
                WHERE day = ?
                """,
                (
                    processed,
                    label_skipped,
                    semantic_used,
                    groq_used,
                    corrections,
                    json.dumps(merged_cats),
                    ts,
                    day_key,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO daily_snapshots
                    (day, processed, label_skipped, semantic_used, groq_used,
                     corrections, top_categories, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    day_key,
                    processed,
                    label_skipped,
                    semantic_used,
                    groq_used,
                    corrections,
                    json.dumps(top_categories or {}),
                    ts,
                ),
            )
        self.conn.commit()

    def list_days(self, limit: int = 30) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT day, processed, label_skipped, semantic_used, groq_used,
                   corrections, top_categories, updated_at
            FROM daily_snapshots
            ORDER BY day DESC
            LIMIT ?
            """,
            (limit,),
        )
        out: List[Dict[str, Any]] = []
        for row in cur.fetchall():
            out.append(
                {
                    "day": row[0],
                    "processed": row[1],
                    "label_skipped": row[2],
                    "semantic_used": row[3],
                    "groq_used": row[4],
                    "corrections": row[5],
                    "top_categories": json.loads(row[6] or "{}"),
                    "updated_at": row[7],
                }
            )
        return out

    def record_cycle_run(
        self,
        *,
        started_at: Optional[str],
        completed_at: str,
        dry_run: bool = False,
        pages_scanned: int = 0,
        fetched_total: int = 0,
        label_skipped: int = 0,
        dedup_skipped: int = 0,
        classified: int = 0,
        actions_applied: int = 0,
        semantic_used: int = 0,
        groq_used: int = 0,
        gmail_fetch_ms: float = 0.0,
        filtering_ms: float = 0.0,
        classify_ms: float = 0.0,
        actions_ms: float = 0.0,
        total_cycle_ms: float = 0.0,
        status: str = "ok",
        semantic_rate: float = 0.0,
        top_categories: Optional[Dict[str, int]] = None,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO cycle_runs (
                started_at, completed_at, dry_run, pages_scanned, fetched_total,
                label_skipped, dedup_skipped, classified, actions_applied,
                semantic_used, groq_used, gmail_fetch_ms, filtering_ms,
                classify_ms, actions_ms, total_cycle_ms, status,
                semantic_rate, top_categories
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at,
                completed_at,
                1 if dry_run else 0,
                pages_scanned,
                fetched_total,
                label_skipped,
                dedup_skipped,
                classified,
                actions_applied,
                semantic_used,
                groq_used,
                gmail_fetch_ms,
                filtering_ms,
                classify_ms,
                actions_ms,
                total_cycle_ms,
                status,
                semantic_rate,
                json.dumps(top_categories or {}),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_historical_totals(self) -> Dict[str, Any]:
        """Cumulative totals across all stored daily snapshots."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                COALESCE(SUM(processed), 0),
                COALESCE(SUM(label_skipped), 0),
                COALESCE(SUM(semantic_used), 0),
                COALESCE(SUM(groq_used), 0),
                COALESCE(SUM(corrections), 0)
            FROM daily_snapshots
            """
        )
        row = cur.fetchone() or (0, 0, 0, 0, 0)
        return {
            "total_processed": int(row[0]),
            "total_label_skipped": int(row[1]),
            "total_semantic_calls": int(row[2]),
            "total_groq_calls": int(row[3]),
            "total_corrections": int(row[4]),
        }

    def list_cycle_runs(self, limit: int = 30) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, started_at, completed_at, dry_run, pages_scanned, fetched_total,
                   label_skipped, dedup_skipped, classified, actions_applied,
                   semantic_used, groq_used, gmail_fetch_ms, filtering_ms,
                   classify_ms, actions_ms, total_cycle_ms, status,
                   semantic_rate, top_categories
            FROM cycle_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        out: List[Dict[str, Any]] = []
        for row in cur.fetchall():
            out.append(self._cycle_row_to_dict(row))
        return out

    def get_latest_cycle_run(self) -> Optional[Dict[str, Any]]:
        runs = self.list_cycle_runs(limit=1)
        return runs[0] if runs else None

    @staticmethod
    def _cycle_row_to_dict(row) -> Dict[str, Any]:
        top = {}
        if len(row) > 19 and row[19]:
            try:
                top = json.loads(row[19])
            except (json.JSONDecodeError, TypeError):
                top = {}
        semantic_rate = float(row[18]) if len(row) > 18 and row[18] is not None else 0.0
        return {
            "id": row[0],
            "started_at": row[1],
            "completed_at": row[2],
            "dry_run": bool(row[3]),
            "pages_scanned": row[4],
            "fetched_total": row[5],
            "label_skipped": row[6],
            "dedup_skipped": row[7],
            "classified": row[8],
            "actions_applied": row[9],
            "semantic_used": row[10],
            "groq_used": row[11],
            "latency": {
                "gmail_fetch_ms": row[12],
                "filtering_ms": row[13],
                "classify_ms": row[14],
                "actions_ms": row[15],
                "total_cycle_ms": row[16],
            },
            "status": row[17],
            "semantic_rate": semantic_rate,
            "top_categories": top,
        }

    def get_day(self, day: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT day, processed, label_skipped, semantic_used, groq_used,
                   corrections, top_categories, updated_at
            FROM daily_snapshots WHERE day=?
            """,
            (day,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "day": row[0],
            "processed": row[1],
            "label_skipped": row[2],
            "semantic_used": row[3],
            "groq_used": row[4],
            "corrections": row[5],
            "top_categories": json.loads(row[6] or "{}"),
            "updated_at": row[7],
        }

    @staticmethod
    def _merge_category_json(
        existing_json: Optional[str],
        new_counts: Optional[Dict[str, int]],
    ) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        if existing_json:
            try:
                merged = {k: int(v) for k, v in json.loads(existing_json).items()}
            except (json.JSONDecodeError, TypeError, ValueError):
                merged = {}
        if new_counts:
            for cat, cnt in new_counts.items():
                merged[cat] = merged.get(cat, 0) + int(cnt)
        return merged


daily_metrics_store = DailyMetricsStore()
