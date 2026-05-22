"""
Central category action policies — archive, mark-read, trash protection.

Classifier decides WHAT; policies decide WHAT TO DO.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
POLICIES_PATH = ROOT_DIR / "category_policies.yaml"


def load_policies(path: Path = POLICIES_PATH) -> Dict[str, Any]:
    """Load category_policies.yaml."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def merge_policies_into_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Overlay policy file onto config: actions, safety, processing limits.

    config.yaml ``actions`` / ``safety`` remain as fallback when policy file missing keys.
    """
    raw = load_policies()
    if not raw:
        return config

    file_policies = raw.get("policies") or {}
    if file_policies:
        merged_actions = dict(config.get("actions") or {})
        for cat, policy in file_policies.items():
            if isinstance(policy, dict):
                merged = {**merged_actions.get(cat, {}), **policy}
                merged["archive"] = False
                merged["trash"] = False
                merged_actions[cat] = merged
        config["actions"] = merged_actions

    for cat, policy in (config.get("actions") or {}).items():
        if isinstance(policy, dict):
            policy["archive"] = False
            policy["trash"] = False

    protected = raw.get("protected") or {}
    safety = dict(config.get("safety") or {})
    if protected.get("never_archive") is not None:
        safety["never_archive"] = list(protected["never_archive"])
    if protected.get("never_trash") is not None:
        safety["never_trash"] = list(protected["never_trash"])
    config["safety"] = safety

    limits = raw.get("processing_limits") or {}
    processing = dict(config.get("processing") or {})
    for key in ("max_actions_per_cycle", "max_trash_per_cycle"):
        if key in limits:
            processing[key] = int(limits[key])
    config["processing"] = processing

    config["category_policies"] = raw
    return config


def get_category_policy(config: Dict[str, Any], category: str) -> Optional[Dict[str, Any]]:
    return (config.get("actions") or {}).get(category)


def never_archive_categories(config: Dict[str, Any]) -> List[str]:
    return list((config.get("safety") or {}).get("never_archive") or [])


def never_trash_categories(config: Dict[str, Any]) -> List[str]:
    return list((config.get("safety") or {}).get("never_trash") or [])


def processing_limits(config: Dict[str, Any]) -> Dict[str, int]:
    proc = config.get("processing") or {}
    safety = config.get("safety") or {}
    return {
        "max_actions_per_run": int(
            proc.get("max_actions_per_cycle")
            or safety.get("max_actions_per_run", 50)
        ),
        "max_trash_per_cycle": int(proc.get("max_trash_per_cycle", 0)),
    }
