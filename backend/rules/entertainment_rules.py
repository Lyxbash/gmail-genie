"""
Entertainment and streaming subscription classification rules.

Maps to ``Promotions`` when subscription/marketing tone is detected,
otherwise ``General`` for pure platform notifications.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import ENTERTAINMENT_DOMAINS
from backend.rules.keyword_lists import ENTERTAINMENT_KEYWORDS, PROMOTION_SECONDARY_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY_PROMO = "Promotions"
CATEGORY_GENERAL = "General"


def classify_entertainment(ctx: EmailContext) -> Optional[dict]:
    """Classify streaming, gaming, and media platform emails."""
    if domain_matches(ctx.domain, ENTERTAINMENT_DOMAINS):
        if contains_any(ctx.combined, PROMOTION_SECONDARY_KEYWORDS):
            return build_result(
                category=CATEGORY_PROMO,
                confidence=0.90,
                reason="entertainment_domain_promotional_tone",
            )
        return build_result(
            category=CATEGORY_GENERAL,
            confidence=0.92,
            reason="matched_entertainment_domain",
        )

    if contains_any(ctx.combined, ENTERTAINMENT_KEYWORDS):
        return build_result(
            category=CATEGORY_GENERAL,
            confidence=0.89,
            reason="matched_entertainment_keywords",
        )

    return None
