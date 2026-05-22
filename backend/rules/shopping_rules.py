"""
Shopping, e-commerce, and food-delivery classification rules.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import FOOD_DELIVERY_DOMAINS, SHOPPING_DOMAINS
from backend.rules.keyword_lists import FOOD_DELIVERY_KEYWORDS, SHOPPING_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY = "Shopping"


def classify_shopping(ctx: EmailContext) -> Optional[dict]:
    """Classify retail orders, shipping updates, and food delivery."""
    if domain_matches(ctx.domain, SHOPPING_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.96,
            reason="matched_shopping_domain",
        )

    if contains_any(ctx.combined, SHOPPING_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.93,
            reason="matched_shopping_keywords",
        )

    if domain_matches(ctx.domain, FOOD_DELIVERY_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.95,
            reason="matched_food_delivery_domain",
        )

    if contains_any(ctx.combined, FOOD_DELIVERY_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.92,
            reason="matched_food_delivery_keywords",
        )

    return None
