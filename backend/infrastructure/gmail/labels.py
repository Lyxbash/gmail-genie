"""
Managed Gmail label registry — single source of truth for incremental processing.

Label paths match ``config.yaml`` ``labels:`` values (nested paths as Gmail names).
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

# Canonical managed label paths (Gmail label ``name`` field values).
# Kept in sync with config.yaml; use ``managed_label_names_from_config`` at runtime.
MANAGED_LABELS: List[str] = [
    "Finance",
    "Finance/Receipts",
    "Jobs/Alerts",
    "Jobs/Applications",
    "Jobs/Recruiters",
    "Content/Newsletters",
    "Marketing/Promotions",
    "Security/Alerts",
    "Social",
    "Documents",
    "Work",
    "Shopping",
    "Travel",
    "Education",
    "General",
]


def managed_label_names_from_config(config: Dict[str, Any]) -> List[str]:
    """Return sorted unique Gmail label paths from config (preferred over static list)."""
    raw = config.get("labels") or {}
    names: Set[str] = set()
    for path in raw.values():
        if path and str(path).strip():
            names.add(str(path).strip())
    if names:
        return sorted(names)
    return list(MANAGED_LABELS)


def category_to_gmail_label(category: str, config: Dict[str, Any]) -> str:
    """Map classifier category to Gmail label path from config."""
    mappings = config.get("labels") or {}
    return mappings.get(category, category)
