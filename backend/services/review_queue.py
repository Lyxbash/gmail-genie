"""
Human review queue — ambiguous or low-trust classifications.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.storage.activity_store import activity_store
from backend.rules.score_margin import review_priority
from backend.api.schemas import ReviewQueueItem

DEFAULT_CONFIDENCE_THRESHOLD = 0.70


def build_review_queue(
    limit: int = 50,
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> List[ReviewQueueItem]:
    """
    Return emails needing human review from persisted activity log.

    Priority: explicit review_reason rows, then low confidence, deduped by message_id.
    """
    threshold = confidence_threshold

    seen: set[str] = set()
    items: List[ReviewQueueItem] = []

    for row in activity_store.list_review_candidates(limit * 2):
        key = row.get("message_id") or f"{row.get('sender')}|{row.get('subject')}"
        if key in seen:
            continue
        seen.add(key)
        items.append(_row_to_review_item(row, row.get("review_reason") or "flagged"))
        if len(items) >= limit:
            return items

    for row in activity_store.list_low_confidence(threshold, limit * 2):
        key = row.get("message_id") or f"{row.get('sender')}|{row.get('subject')}"
        if key in seen:
            continue
        seen.add(key)
        items.append(_row_to_review_item(row, "low_confidence"))
        if len(items) >= limit:
            break

    items.sort(key=lambda item: review_priority(item.reason))
    return items[:limit]


def _row_to_review_item(row: Dict[str, Any], reason: str) -> ReviewQueueItem:
    return ReviewQueueItem(
        message_id=row.get("message_id"),
        sender=row.get("sender") or "",
        subject=row.get("subject") or "",
        snippet=row.get("snippet") or "",
        predicted_category=row.get("category", "General"),
        confidence=float(row.get("confidence", 0)),
        source=row.get("source", "rules"),
        reason=reason,
        score_margin=row.get("score_margin"),
        top_score=row.get("top_score"),
        second_category=row.get("second_category"),
    )
