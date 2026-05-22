"""
Dependency health checks (no secrets).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict

from backend.config import load_config
from backend.paths import BACKEND_DATA_DIR, PROJECT_DATA_DIR


def check_databases() -> bool:
    paths = [
        BACKEND_DATA_DIR / "corrections.db",
        PROJECT_DATA_DIR / "cache.db",
        BACKEND_DATA_DIR / "activity.db",
        BACKEND_DATA_DIR / "daily_metrics.db",
    ]
    try:
        for path in paths:
            if path.is_file():
                conn = sqlite3.connect(str(path))
                conn.execute("SELECT 1")
                conn.close()
        return True
    except sqlite3.Error:
        return False


def check_gmail_connected(gmail_client: Any) -> bool:
    try:
        if gmail_client and getattr(gmail_client, "service", None):
            gmail_client.service.users().getProfile(userId="me").execute()
            return True
    except Exception:
        pass
    return False


def check_ollama_available() -> bool:
    try:
        import ollama

        ollama.list()
        return True
    except Exception:
        return False


def build_health_status(gmail_client: Any) -> Dict[str, Any]:
    """Delegate to cached health service."""
    from backend.infrastructure.health.health_service import build_health_status as _cached_health

    return _cached_health(gmail_client)


def build_config_summary() -> Dict[str, Any]:
    cfg = load_config()
    llm = cfg.get("llm") or {}
    app_cfg = cfg.get("app") or {}
    proc = cfg.get("processing") or {}
    safety = cfg.get("safety") or {}

    label_map = cfg.get("labels") or {}
    label_paths = sorted({str(v).strip() for v in label_map.values() if v})

    return {
        "provider": llm.get("provider", "ollama"),
        "model": llm.get("model", ""),
        "label_paths": label_paths,
        "categories": list(cfg.get("categories") or []),
        "thresholds": {
            "confidence_threshold": float(app_cfg.get("confidence_threshold", 0.70)),
            "rule_high_confidence": float(llm.get("rule_high_confidence", 0.95)),
            "rule_medium_confidence": float(llm.get("rule_medium_confidence", 0.70)),
            "semantic_accept_confidence": float(
                llm.get("semantic_accept_confidence", 0.70)
            ),
            "groq_escalation_confidence": float(
                llm.get("groq_escalation_confidence", 0.55)
            ),
        },
        "limits": {
            "max_emails": int(app_cfg.get("max_emails", 25)),
            "max_actions_per_run": int(safety.get("max_actions_per_run", 50)),
            "max_actions_per_cycle": int(proc.get("max_actions_per_cycle", 50)),
            "max_trash_per_cycle": int(proc.get("max_trash_per_cycle", 0)),
        },
        "features": {
            "rule_verify_enabled": bool(llm.get("rule_verify_enabled", True)),
            "escalation_enabled": bool(llm.get("escalation_enabled", True)),
            "deduplicate": bool(proc.get("deduplicate", True)),
            "unread_only": bool(proc.get("unread_only", False)),
        },
        "categories": list(cfg.get("categories") or []),
    }
