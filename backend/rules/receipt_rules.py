"""
Receipt and payment-confirmation classification rules.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.keyword_lists import RECEIPT_KEYWORDS
from backend.rules.result_builder import EmailContext, build_result, contains_any

CATEGORY = "Receipts"

SENDER_RECEIPT_OVERRIDES = [
    "googleplay-noreply@google.com",
]


def classify_receipts(ctx: EmailContext) -> Optional[dict]:
    """Classify invoices, receipts, and payment confirmations."""
    # Sender specializations — avoid broad-domain collisions (e.g., Google).
    if any(s in ctx.sender_lower for s in SENDER_RECEIPT_OVERRIDES):
        return build_result(
            category=CATEGORY,
            confidence=0.98,
            reason="sender_receipt_override",
        )

    if contains_any(ctx.combined, RECEIPT_KEYWORDS):
        # Strong receipt signals in subject increase confidence
        if any(
            token in ctx.subject_lower
            for token in ("receipt", "invoice", "payment")
        ):
            return build_result(
                category=CATEGORY,
                confidence=0.96,
                reason="matched_receipt_subject_keywords",
            )
        return build_result(
            category=CATEGORY,
            confidence=0.93,
            reason="matched_receipt_keywords",
        )

    return None
