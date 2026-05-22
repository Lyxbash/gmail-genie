"""
APScheduler-based automatic inbox cycles (optional, config-driven).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import load_config
from backend.services.cycle_manager import cycle_manager
from backend.services.cycle_runner import execute_inbox_cycle
from backend.infrastructure.logging.logging_setup import get_cycle_logger

_log = logging.getLogger(__name__)
_cycle_log = get_cycle_logger()

_scheduler: Optional[BackgroundScheduler] = None
_state: Dict[str, Any] = {
    "enabled": False,
    "interval_minutes": 0,
    "dry_run": True,
    "target_actionable": 25,
    "total_runs": 0,
    "total_skipped": 0,
    "last_run": None,
    "last_skip": None,
    "next_run": None,
    "last_error": None,
}


def _scheduled_job(gmail, classifier) -> None:
    if cycle_manager.is_running():
        _state["total_skipped"] += 1
        _state["last_skip"] = datetime.now(timezone.utc).isoformat()
        _cycle_log.info("Scheduler skipped — cycle already active")
        return

    if not cycle_manager.try_acquire():
        _state["total_skipped"] += 1
        _state["last_skip"] = datetime.now(timezone.utc).isoformat()
        _cycle_log.info("Scheduler skipped — could not acquire lock")
        return

    try:
        cfg = load_config()
        sched = cfg.get("scheduler") or {}
        execute_inbox_cycle(
            gmail,
            classifier,
            dry_run=bool(sched.get("dry_run", True)),
            max_results=int(sched.get("target_actionable", 25)),
            force_reprocess=False,
            verbose=False,
            compact_report=False,
            trigger="scheduler",
        )
        _state["total_runs"] += 1
        _state["last_run"] = datetime.now(timezone.utc).isoformat()
        _state["last_error"] = None
    except Exception as exc:
        _state["last_error"] = str(exc)
        cycle_manager.mark_failed(str(exc))
        _log.exception("Scheduled cycle failed")
    finally:
        cycle_manager.release()


def start_scheduler(gmail, classifier) -> None:
    global _scheduler
    stop_scheduler()

    cfg = load_config()
    sched_cfg = cfg.get("scheduler") or {}
    if not bool(sched_cfg.get("enabled", False)):
        _state["enabled"] = False
        _log.info("Inbox scheduler disabled in config")
        return

    interval = max(5, int(sched_cfg.get("interval_minutes", 15)))
    _state.update(
        {
            "enabled": True,
            "interval_minutes": interval,
            "dry_run": bool(sched_cfg.get("dry_run", True)),
            "target_actionable": int(sched_cfg.get("target_actionable", 25)),
        }
    )

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _scheduled_job,
        trigger=IntervalTrigger(minutes=interval),
        args=[gmail, classifier],
        id="gmail_genie_inbox_cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    job = _scheduler.get_job("gmail_genie_inbox_cycle")
    if job and job.next_run_time:
        _state["next_run"] = job.next_run_time.isoformat()
    _log.info("Inbox scheduler started (every %d minutes)", interval)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    _state["next_run"] = None


def scheduler_status() -> Dict[str, Any]:
    running = bool(_scheduler and _scheduler.running)
    if running:
        job = _scheduler.get_job("gmail_genie_inbox_cycle")
        if job and job.next_run_time:
            _state["next_run"] = job.next_run_time.isoformat()
    return {
        "enabled": _state.get("enabled", False),
        "running": running,
        "interval_minutes": _state.get("interval_minutes"),
        "dry_run": _state.get("dry_run"),
        "target_actionable": _state.get("target_actionable"),
        "last_run": _state.get("last_run"),
        "last_skip": _state.get("last_skip"),
        "next_run": _state.get("next_run"),
        "total_runs": _state.get("total_runs", 0),
        "total_skipped": _state.get("total_skipped", 0),
        "last_error": _state.get("last_error"),
        "cycle_active": cycle_manager.is_running(),
    }
