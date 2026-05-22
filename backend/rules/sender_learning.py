"""
Lightweight sender correction bias for scored rules.

Applies a fixed point boost after repeated user corrections — no ML, no embeddings.
"""

from __future__ import annotations

from typing import Dict

from backend.storage.corrections_store import (
    SENDER_OVERRIDE_BLOCKED_CATEGORIES,
    corrections_store,
)
from backend.rules.result_builder import EmailContext
from backend.rules.scoring import CategoryScore, has_transactional_block


def apply_sender_correction_boost(
    scores: Dict[str, CategoryScore],
    ctx: EmailContext,
) -> None:
    """
    Boost category score for senders with enough consistent user corrections.

    Skipped when transactional signals are present (receipts/refunds/OTP win).
    """
    if has_transactional_block(ctx.combined):
        return

    override = corrections_store.get_sender_override(ctx.sender)
    if not override:
        return

    category = override["category"]
    if category in SENDER_OVERRIDE_BLOCKED_CATEGORIES:
        return
    if category not in scores:
        return

    scores[category].add_positive(
        int(override["boost"]),
        f"sender_correction_boost:{override['count']}",
    )
