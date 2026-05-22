"""
User-facing setup checklist for local MVP onboarding.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import CONFIG_PATH, load_config
from backend.storage.cycle_undo_store import cycle_undo_store
from backend.infrastructure.gmail.gmail_client import CREDENTIALS_PATH, TOKEN_PATH
from backend.infrastructure.gmail.labels import managed_label_names_from_config
from backend.services.scheduler import scheduler_status


def _check_oauth_files() -> bool:
    return CREDENTIALS_PATH.is_file() and TOKEN_PATH.is_file()


def _check_model_available(cfg: Dict[str, Any]) -> tuple[bool, str]:
    model = str((cfg.get("llm") or {}).get("model", "")).strip()
    if not model:
        return False, ""
    try:
        import ollama

        names: List[str] = []
        for item in ollama.list().get("models", []):
            name = item.get("model") or item.get("name") or ""
            if name:
                names.append(name.split(":")[0] if ":" in name else name)
                names.append(name)
        if model in names or any(model in n or n.startswith(model) for n in names):
            return True, model
        return False, model
    except Exception:
        return False, model


def _check_labels_initialized(gmail_client: Any) -> bool:
    if not gmail_client or not getattr(gmail_client, "service", None):
        return False
    try:
        cfg = load_config()
        expected = set(managed_label_names_from_config(cfg))
        if hasattr(gmail_client, "get_existing_labels"):
            existing = set(gmail_client.get_existing_labels(force_refresh=False).keys())
            return bool(expected & existing) or len(existing) > 5
        return False
    except Exception:
        return False


def build_onboarding_status(
    gmail_client: Any,
    health: Dict[str, Any],
) -> Dict[str, Any]:
    cfg = load_config()
    sched = scheduler_status()
    model_ok, model_name = _check_model_available(cfg)
    oauth_ok = _check_oauth_files()
    labels_ok = _check_labels_initialized(gmail_client) if health.get("gmail_connected") else False

    items: List[Dict[str, Any]] = [
        {
            "id": "gmail_connected",
            "label": "Gmail connected",
            "ok": bool(health.get("gmail_connected")),
            "hint": "Complete OAuth in browser (see README)",
        },
        {
            "id": "oauth_valid",
            "label": "OAuth credentials",
            "ok": oauth_ok,
            "hint": "Place credentials.json and run one-time auth",
        },
        {
            "id": "ollama_running",
            "label": "Ollama running",
            "ok": bool(health.get("ollama_available")),
            "hint": "Install Ollama and keep it running locally",
        },
        {
            "id": "model_available",
            "label": "Model available",
            "ok": model_ok,
            "hint": f"Pull model: ollama pull {model_name or 'mistral'}",
            "detail": model_name or None,
        },
        {
            "id": "labels_initialized",
            "label": "Labels initialized",
            "ok": labels_ok,
            "hint": "Run a dry cycle once — Genie creates Gmail labels on apply",
        },
        {
            "id": "scheduler_configured",
            "label": "Scheduler configured",
            "ok": bool(sched.get("enabled")),
            "hint": "Enable scheduler in config.yaml (optional)",
            "detail": sched.get("interval_minutes"),
        },
    ]

    required_ok = all(
        i["ok"]
        for i in items
        if i["id"] in ("gmail_connected", "oauth_valid", "ollama_running", "model_available")
    )

    undo = cycle_undo_store.get_last_cycle()

    return {
        "success": True,
        "ready": required_ok,
        "items": items,
        "environment": (cfg.get("app") or {}).get("environment", "development"),
        "config_present": CONFIG_PATH.is_file(),
        "last_undoable_cycle": undo if undo and undo.get("can_undo") else None,
        "privacy_note": "Email content is processed locally; Gmail API is the only cloud touchpoint.",
    }
