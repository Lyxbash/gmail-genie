"""
Cached health checks with degraded/failed semantics (avoid hammering Gmail).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import load_config
from backend.services.cycle_manager import cycle_manager

_log = logging.getLogger(__name__)

from backend.paths import BACKEND_DATA_DIR, PROJECT_DATA_DIR

_CACHE: Dict[str, Any] = {}
_CACHE_TS: float = 0.0
_DEFAULT_TTL = 45
_GMAIL_CHECK_TIMEOUT = 8.0


def _check_databases() -> bool:
    paths = [
        BACKEND_DATA_DIR / "corrections.db",
        PROJECT_DATA_DIR / "cache.db",
        BACKEND_DATA_DIR / "activity.db",
        BACKEND_DATA_DIR / "daily_metrics.db",
    ]
    try:
        for path in paths:
            if path.is_file():
                conn = sqlite3.connect(str(path), timeout=2)
                conn.execute("SELECT 1")
                conn.close()
        return True
    except sqlite3.Error:
        return False


def _check_gmail_isolated(gmail_client: Any) -> tuple[bool, Optional[str]]:
    """Profile check in a thread with short timeout."""
    if not gmail_client or not getattr(gmail_client, "service", None):
        return False, None
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout

    def _probe() -> None:
        gmail_client.service.users().getProfile(userId="me").execute()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_probe).result(timeout=_GMAIL_CHECK_TIMEOUT)
        return True, datetime.now(timezone.utc).isoformat()
    except FutTimeout:
        _log.warning("Gmail health probe timed out after %ss", _GMAIL_CHECK_TIMEOUT)
        return False, _CACHE.get("last_gmail_ok_at")
    except Exception as exc:
        _log.debug("Gmail health probe failed: %s", exc)
        return False, _CACHE.get("last_gmail_ok_at")


def _check_ollama() -> bool:
    try:
        import ollama

        ollama.list()
        return True
    except Exception:
        return False


def build_health_status(gmail_client: Any, *, force_refresh: bool = False) -> Dict[str, Any]:
    cfg = load_config()
    health_cfg = cfg.get("health") or {}
    ttl = int(health_cfg.get("cache_ttl_seconds", _DEFAULT_TTL))
    now = time.time()

    if not force_refresh and _CACHE and (now - _CACHE_TS) < ttl:
        cached = dict(_CACHE)
        cached["cached"] = True
        return cached

    llm = cfg.get("llm") or {}
    import os

    groq_enabled = bool(llm.get("escalation_enabled")) and bool(
        llm.get("groq_api_key") or os.environ.get("GROQ_API_KEY")
    )

    gmail_ok, gmail_ts = _check_gmail_isolated(gmail_client)
    if gmail_ok and gmail_ts:
        _CACHE["last_gmail_ok_at"] = gmail_ts

    ollama_ok = _check_ollama()
    db_ok = _check_databases()

    last_cycle = cycle_manager.last_successful_cycle()
    last_cycle_at = (last_cycle or {}).get("completed_at")

    if not db_ok:
        status = "failed"
    elif not gmail_ok:
        status = "degraded" if _CACHE.get("last_gmail_ok_at") else "failed"
    elif not ollama_ok and groq_enabled:
        status = "degraded"
    elif not ollama_ok:
        status = "degraded"
    else:
        status = "ok"

    result = {
        "status": status,
        "gmail_connected": gmail_ok,
        "ollama_available": ollama_ok,
        "groq_enabled": groq_enabled,
        "groq_configured": groq_enabled,
        "database_ok": db_ok,
        "cached": False,
        "last_gmail_ok_at": _CACHE.get("last_gmail_ok_at"),
        "last_successful_cycle_at": last_cycle_at,
        "cycle_running": cycle_manager.is_running(),
        "details": {
            "provider": llm.get("provider", "ollama"),
            "model": llm.get("model", ""),
            "environment": (cfg.get("app") or {}).get("environment", "development"),
        },
    }

    _CACHE.clear()
    _CACHE.update(result)
    globals()["_CACHE_TS"] = now
    return result
