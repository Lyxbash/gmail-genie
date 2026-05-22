"""
Promotional and marketing email classification rules.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.keyword_lists import PROMOTION_KEYWORDS, PROMOTION_SECONDARY_KEYWORDS
from backend.rules.result_builder import EmailContext, build_result, contains_any

CATEGORY = "Promotions"


def classify_promotions(ctx: EmailContext) -> Optional[dict]:
    """Classify sales campaigns, coupons, and marketing blasts."""
    # Negative guard: newsletters/digests often contain light marketing language,
    # but should not be classified as Promotions.
    if contains_any(
        ctx.subject_lower,
        [
            "newsletter",
            "digest",
            "weekly",
            "daily",
            "roundup",
            "edition",
            "the batch",
            "application received",
            "interview",
            "recruiter",
            "security alert",
            "refund",
            "receipt",
            "invoice",
        ],
    ):
        return None

    if contains_any(ctx.combined, PROMOTION_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.96,
            reason="matched_sale_keywords",
        )

    if contains_any(ctx.combined, PROMOTION_SECONDARY_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.90,
            reason="matched_promotion_secondary_keywords",
        )

    return None
