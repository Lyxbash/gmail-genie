"""
Application configuration loader.

Loads ``config.yaml`` and environment variables from the project root ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
ENV_PATH = ROOT_DIR / ".env"

DEFAULT_GMAIL_QUERY = "newer_than:14d -in:sent -in:chats"
GMAIL_QUERY_EXCLUDES = "-in:sent -in:chats"

# Preset day ranges for "Organize my recent emails" UX (maps to Gmail search).
ORGANIZE_DAY_PRESETS = (1, 3, 7, 14)

_OPENAPI_PLACEHOLDER_QUERIES = frozenset(
    {"string", "null", "none", "undefined", "example"}
)

load_dotenv(ENV_PATH)


def get_environment(config: Optional[Dict[str, Any]] = None) -> str:
    """Resolve environment: APP_ENVIRONMENT env → config app.environment."""
    env_override = (os.environ.get("APP_ENVIRONMENT") or "").strip().lower()
    if env_override:
        return env_override
    if config is None:
        config = load_config()
    return str((config.get("app") or {}).get("environment", "development")).strip().lower()


def is_production(config: Optional[Dict[str, Any]] = None) -> bool:
    return get_environment(config) == "production"


def get_cors_origins(config: Optional[Dict[str, Any]] = None) -> List[str]:
    raw = (os.environ.get("FRONTEND_ORIGIN") or "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    if is_production(config):
        return []
    return ["*"]


def load_config() -> Dict[str, Any]:
    """Load YAML config merged with relevant environment overrides."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    app = config.setdefault("app", {})
    if os.environ.get("APP_ENVIRONMENT"):
        app["environment"] = get_environment(config)

    llm = config.setdefault("llm", {})
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        llm["groq_api_key"] = groq_key
    groq_model = os.environ.get("GROQ_MODEL", "").strip()
    if groq_model:
        llm["escalation_model"] = groq_model

    gmail = config.setdefault("gmail", {})
    if os.environ.get("GMAIL_HTTP_TIMEOUT_SECONDS"):
        try:
            gmail["http_timeout_seconds"] = int(
                os.environ["GMAIL_HTTP_TIMEOUT_SECONDS"]
            )
        except ValueError:
            pass

    from backend.policies import merge_policies_into_config

    return merge_policies_into_config(config)


def resolve_gmail_query(
    request_query: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    if config is None:
        config = load_config()

    req = (request_query or "").strip()
    if req.lower() in _OPENAPI_PLACEHOLDER_QUERIES:
        req = ""

    app_cfg = config.get("app") or {}
    cfg_query = (app_cfg.get("gmail_query") or "").strip()
    if cfg_query.lower() in _OPENAPI_PLACEHOLDER_QUERIES:
        cfg_query = ""

    resolved = req or cfg_query or DEFAULT_GMAIL_QUERY

    processing_cfg = config.get("processing") or {}
    if bool(processing_cfg.get("unread_only", False)):
        if "is:unread" not in resolved:
            resolved = f"{resolved} is:unread".strip()

    return resolved


def build_organize_gmail_query(
    *,
    days: Optional[int] = None,
    custom_query: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build a user-facing "organize recent mail" Gmail query without changing scan logic.
    """
    custom = (custom_query or "").strip()
    if custom:
        return resolve_gmail_query(custom, config)
    if days is not None and int(days) in ORGANIZE_DAY_PRESETS:
        base = f"newer_than:{int(days)}d {GMAIL_QUERY_EXCLUDES}".strip()
        return resolve_gmail_query(base, config)
    return resolve_gmail_query(None, config)


def validate_config_structure(config: Dict[str, Any]) -> None:
    if not config.get("categories"):
        raise ValueError("config.yaml: categories list is required")
    if "labels" not in config:
        raise ValueError("config.yaml: labels section is required")
    proc = config.setdefault("processing", {})
    defaults = {
        "target_unprocessed_per_cycle": 25,
        "gmail_page_size": 25,
        "max_scan_pages": 10,
    }
    for key, default in defaults.items():
        proc.setdefault(key, default)
    sched = config.setdefault("scheduler", {})
    sched.setdefault("enabled", False)
    sched.setdefault("interval_minutes", 15)
