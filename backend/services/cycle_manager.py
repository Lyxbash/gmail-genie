"""
Global inbox cycle lock and live operational state (in-process, thread-safe).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional

_log = logging.getLogger(__name__)

from backend.paths import BACKEND_DATA_DIR

STATE_PATH = BACKEND_DATA_DIR / "last_cycle.json"

STAGE_SCANNING = "scanning"
STAGE_SKIPPING = "skipping_labelled"
STAGE_CLASSIFYING = "classifying"
STAGE_APPLYING = "applying_actions"
STAGE_COMPLETE = "complete"
STAGE_FAILED = "failed"
STAGE_IDLE = "idle"

# Cycle lifecycle (API / frontend)
STATE_RUNNING = "running"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"
STATE_PARTIAL_SUCCESS = "partial_success"
STATE_TIMED_OUT = "timed_out"
STATE_IDLE = "idle"

STALL_HEARTBEAT_SECONDS = 60


class CycleBusyError(Exception):
    """Raised when a second cycle is requested while one is active."""


class CycleManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._running = False
        self._started_at: Optional[str] = None
        self._last_progress_at: Optional[str] = None
        self._current_stage = STAGE_IDLE
        self._cycle_state = STATE_IDLE
        self._progress: Dict[str, Any] = {}
        self._last_error: Optional[str] = None
        self._last_success: Optional[Dict[str, Any]] = None
        self._load_last_success()

    def _load_last_success(self) -> None:
        if not STATE_PATH.is_file():
            return
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._last_success = data
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    def _save_last_success(self, payload: Dict[str, Any]) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._last_success = payload

    def _touch_progress(self) -> None:
        self._last_progress_at = datetime.now(timezone.utc).isoformat()

    def _elapsed_seconds(self) -> Optional[float]:
        if not self._started_at:
            return None
        try:
            started = datetime.fromisoformat(self._started_at.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - started).total_seconds()
        except (ValueError, TypeError):
            return None

    def _heartbeat_stale(self) -> bool:
        if not self._running or not self._last_progress_at:
            return False
        try:
            last = datetime.fromisoformat(
                self._last_progress_at.replace("Z", "+00:00")
            )
            return (
                datetime.now(timezone.utc) - last
            ).total_seconds() > STALL_HEARTBEAT_SECONDS
        except (ValueError, TypeError):
            return False

    def try_acquire(self) -> bool:
        acquired = self._run_lock.acquire(blocking=False)
        if not acquired:
            return False
        with self._lock:
            if self._running:
                self._run_lock.release()
                return False
            self._running = True
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._last_progress_at = self._started_at
            self._current_stage = STAGE_SCANNING
            self._cycle_state = STATE_RUNNING
            self._progress = {}
            self._last_error = None
        return True

    def release(self) -> None:
        with self._lock:
            self._running = False
            if self._cycle_state == STATE_RUNNING:
                self._cycle_state = STATE_IDLE
            if self._current_stage not in (STAGE_COMPLETE, STAGE_FAILED):
                self._current_stage = STAGE_IDLE
        try:
            self._run_lock.release()
        except RuntimeError:
            pass

    def set_stage(self, stage: str) -> None:
        with self._lock:
            if self._running:
                self._current_stage = stage
                self._touch_progress()

    def update_progress(
        self,
        *,
        pages_scanned: Optional[int] = None,
        fetched_total: Optional[int] = None,
        label_skipped: Optional[int] = None,
        dedup_skipped: Optional[int] = None,
        classified: Optional[int] = None,
        partial_fetch_failures: Optional[int] = None,
    ) -> None:
        with self._lock:
            if not self._running:
                return
            self._touch_progress()
            if pages_scanned is not None:
                self._progress["pages_scanned"] = pages_scanned
            if fetched_total is not None:
                self._progress["fetched_total"] = fetched_total
            if label_skipped is not None:
                self._progress["label_skipped"] = label_skipped
            if dedup_skipped is not None:
                self._progress["dedup_skipped"] = dedup_skipped
            if classified is not None:
                self._progress["classified"] = classified
            if partial_fetch_failures is not None:
                self._progress["partial_fetch_failures"] = partial_fetch_failures

    def mark_failed(self, message: str, *, timed_out: bool = False) -> None:
        with self._lock:
            self._last_error = message
            self._current_stage = STAGE_FAILED
            self._cycle_state = STATE_TIMED_OUT if timed_out else STATE_FAILED
            self._touch_progress()
        _log.error("Inbox cycle failed: %s", message)

    def mark_complete(self, summary: Dict[str, Any]) -> None:
        partial = int(summary.get("partial_fetch_failures") or 0)
        with self._lock:
            self._current_stage = STAGE_COMPLETE
            self._cycle_state = (
                STATE_PARTIAL_SUCCESS if partial > 0 else STATE_COMPLETED
            )
            completed_at = datetime.now(timezone.utc).isoformat()
            payload = {
                **summary,
                "started_at": self._started_at,
                "completed_at": completed_at,
                "cycle_state": self._cycle_state,
                "status": "partial_success" if partial > 0 else "ok",
            }
            self._last_success = payload
            self._touch_progress()
        self._save_last_success(payload)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = self._elapsed_seconds()
            stale = self._heartbeat_stale()
            out: Dict[str, Any] = {
                "running": self._running,
                "cycle_state": self._cycle_state if self._running else STATE_IDLE,
                "started_at": self._started_at,
                "last_progress_at": self._last_progress_at,
                "elapsed_seconds": round(elapsed, 1) if elapsed is not None else None,
                "heartbeat_stale": stale,
                "current_stage": self._current_stage if self._running else STAGE_IDLE,
                "error": self._last_error,
                **self._progress,
            }
            if not self._running and self._last_success:
                out["last_successful_cycle"] = self._last_success
            return out

    def last_successful_cycle(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._last_success) if self._last_success else None

    def clear_awaiting_apply(self) -> None:
        """User dismissed preview — keep last run stats but hide apply bar."""
        with self._lock:
            if not self._last_success or not self._last_success.get("awaiting_apply"):
                return
            updated = {**self._last_success, "awaiting_apply": False}
            self._last_success = updated
        self._save_last_success(updated)

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @contextmanager
    def cycle_context(self) -> Generator["CycleManager", None, None]:
        if not self.try_acquire():
            raise CycleBusyError("Inbox processing already running")
        try:
            yield self
        except Exception as exc:
            timed_out = "timed out" in str(exc).lower()
            self.mark_failed(str(exc), timed_out=timed_out)
            raise
        finally:
            self.release()


cycle_manager = CycleManager()
