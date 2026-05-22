"""
Display metadata for categories (frontend-ready, backend-only for now).
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.policies import never_trash_categories


_CATEGORY_META: Dict[str, Dict[str, Any]] = {
    "Security Alerts": {
        "display_name": "Security Alerts",
        "icon": "shield",
        "color": "#EF4444",
        "priority": 1,
    },
    "Receipts": {
        "display_name": "Receipts",
        "icon": "receipt",
        "color": "#10B981",
        "priority": 2,
    },
    "Finance": {
        "display_name": "Finance",
        "icon": "bank",
        "color": "#059669",
        "priority": 3,
    },
    "Job Applications/Referrals": {
        "display_name": "Job Applications",
        "icon": "briefcase",
        "color": "#8B5CF6",
        "priority": 4,
    },
    "Job Alerts": {
        "display_name": "Job Alerts",
        "icon": "bell",
        "color": "#7C3AED",
        "priority": 5,
    },
    "Recruiters": {
        "display_name": "Recruiters",
        "icon": "users",
        "color": "#6366F1",
        "priority": 6,
    },
    "Newsletters": {
        "display_name": "Newsletters",
        "icon": "newsletter",
        "color": "#3B82F6",
        "priority": 7,
    },
    "Promotions": {
        "display_name": "Promotions",
        "icon": "tag",
        "color": "#F59E0B",
        "priority": 8,
    },
    "Social": {
        "display_name": "Social",
        "icon": "share",
        "color": "#0EA5E9",
        "priority": 9,
    },
    "Docs": {
        "display_name": "Documents",
        "icon": "file",
        "color": "#64748B",
        "priority": 10,
    },
    "Work": {
        "display_name": "Work",
        "icon": "calendar",
        "color": "#475569",
        "priority": 11,
    },
    "Shopping": {
        "display_name": "Shopping",
        "icon": "cart",
        "color": "#EC4899",
        "priority": 12,
    },
    "Travel": {
        "display_name": "Travel",
        "icon": "plane",
        "color": "#14B8A6",
        "priority": 13,
    },
    "Education": {
        "display_name": "Education",
        "icon": "book",
        "color": "#A855F7",
        "priority": 14,
    },
    "Personal": {
        "display_name": "Personal",
        "icon": "user",
        "color": "#84CC16",
        "priority": 15,
    },
    "General": {
        "display_name": "General",
        "icon": "inbox",
        "color": "#9CA3AF",
        "priority": 99,
    },
}


def get_category_metadata(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return metadata for all configured categories."""
    never_tr = set(never_trash_categories(config))
    categories: List[str] = config.get("categories") or list(_CATEGORY_META.keys())
    out: Dict[str, Dict[str, Any]] = {}
    for cat in categories:
        base = dict(_CATEGORY_META.get(cat, _CATEGORY_META["General"]))
        base["display_name"] = base.get("display_name", cat)
        base["inbox_preserved"] = True
        base["protected"] = cat in never_tr
        base["never_trash"] = cat in never_tr
        out[cat] = base
    return out


def get_category_display(category: str) -> Dict[str, Any]:
    return dict(_CATEGORY_META.get(category, _CATEGORY_META["General"]))
