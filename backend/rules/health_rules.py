"""
Health, wellness, and pharmacy classification rules.

Maps to ``Personal`` (closest config category for health-related mail).
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import HEALTH_DOMAINS
from backend.rules.keyword_lists import HEALTH_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY = "Personal"


def classify_health(ctx: EmailContext) -> Optional[dict]:
    """Classify medical appointments, labs, and pharmacy orders."""
    if domain_matches(ctx.domain, HEALTH_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.93,
            reason="matched_health_domain",
        )

    if contains_any(ctx.combined, HEALTH_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.90,
            reason="matched_health_keywords",
        )

    return None
