"""
Startup validation for local/production deployment.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from backend.config import CONFIG_PATH, get_environment, is_production, load_config, validate_config_structure
from backend.paths import (
    BACKEND_DATA_DIR,
    BACKEND_DEBUG_TRACES_DIR,
    BACKEND_EVAL_DIR,
    BACKEND_LOGS_DIR,
    PROJECT_DATA_DIR,
    ROOT_DIR,
)

_log = logging.getLogger(__name__)

DATA_DIRS = (
    PROJECT_DATA_DIR,
    BACKEND_DATA_DIR,
    BACKEND_LOGS_DIR,
    BACKEND_EVAL_DIR,
    BACKEND_DEBUG_TRACES_DIR,
)


def ensure_directories() -> None:
    for path in DATA_DIRS:
        path.mkdir(parents=True, exist_ok=True)


def _init_sqlite_stores() -> None:
    from backend.storage.activity_store import activity_store
    from backend.storage.corrections_store import corrections_store
    from backend.storage.cycle_undo_store import cycle_undo_store
    from backend.storage.daily_metrics_store import daily_metrics_store
    from backend.storage.processed_store import ProcessedEmailStore

    ProcessedEmailStore()
    cycle_undo_store._init_db()
    activity_store.conn.execute("SELECT 1")
    corrections_store.conn.execute("SELECT 1")
    daily_metrics_store.conn.execute("SELECT 1")


def _check_gmail() -> bool:
    try:
        from backend.infrastructure.health.health_service import _check_gmail_isolated
        from backend.infrastructure.gmail.gmail_client import GmailClient

        client = GmailClient()
        ok, _ = _check_gmail_isolated(client)
        return ok
    except Exception as exc:
        _log.warning("Gmail auth check failed: %s", exc)
        return False


def _check_ollama() -> bool:
    try:
        import ollama

        ollama.list()
        return True
    except Exception as exc:
        _log.warning("Ollama not available (degraded mode): %s", exc)
        return False


def configure_logging(config: Dict[str, Any]) -> None:
    from backend.infrastructure.logging.logging_setup import setup_logging

    setup_logging(production=is_production(config))


def run_startup_validation(*, strict: bool = False) -> Dict[str, Any]:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")

    config = load_config()
    validate_config_structure(config)
    configure_logging(config)
    ensure_directories()

    results: Dict[str, Any] = {
        "config_ok": True,
        "directories_ok": True,
        "database_ok": False,
        "gmail_connected": False,
        "ollama_available": False,
        "environment": get_environment(config),
    }

    try:
        _init_sqlite_stores()
        results["database_ok"] = True
    except Exception as exc:
        _log.error("Database init failed: %s", exc)
        if strict:
            raise

    results["gmail_connected"] = _check_gmail()
    results["ollama_available"] = _check_ollama()

    issues: List[str] = []
    if not results["gmail_connected"]:
        issues.append(
            "Gmail OAuth not ready (backend/credentials.json + token.json)"
        )
    if not results["database_ok"]:
        issues.append("SQLite stores failed to initialize")
    if not results["ollama_available"]:
        issues.append("Ollama unavailable — semantic verify may fail (Groq optional)")

    results["ok"] = results["database_ok"]
    results["issues"] = issues

    if results["ok"] and results["gmail_connected"]:
        _log.info(
            "Startup validation OK (env=%s, ollama=%s)",
            results["environment"],
            results["ollama_available"],
        )
    else:
        msg = "Startup validation: " + "; ".join(issues or ["partial"])
        if strict and not results["gmail_connected"]:
            raise RuntimeError(msg)
        _log.warning(msg)

    return results
