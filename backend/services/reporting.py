"""
Compact operational reports for API responses.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


def build_compact_cycle_report(
    *,
    fetched: int,
    classified: int,
    label_skipped: int,
    dedup_skipped: int = 0,
    semantic_used: int = 0,
    groq_used: int = 0,
    actions_applied: int = 0,
    classifications: Optional[List[Dict[str, Any]]] = None,
    dry_run: bool = False,
    pages_scanned: int = 0,
    fetched_total: Optional[int] = None,
    actionable_found: Optional[int] = None,
) -> Dict[str, Any]:
    """Production-friendly summary for daily cycle and dry-run previews."""
    top_categories: Dict[str, int] = {}
    if classifications:
        counts = Counter(c.get("category", "General") for c in classifications)
        top_categories = dict(counts.most_common(10))

    n = classified or 1
    ft = fetched_total if fetched_total is not None else fetched
    af = actionable_found if actionable_found is not None else classified
    return {
        "pages_scanned": pages_scanned,
        "fetched_total": ft,
        "fetched": ft,
        "actionable_found": af,
        "classified": classified,
        "label_skipped": label_skipped,
        "dedup_skipped": dedup_skipped,
        "semantic_used": semantic_used,
        "groq_used": groq_used,
        "semantic_rate": round(semantic_used / n, 4),
        "groq_rate": round(groq_used / n, 4),
        "actions_applied": actions_applied,
        "dry_run": dry_run,
        "top_categories": top_categories,
    }
