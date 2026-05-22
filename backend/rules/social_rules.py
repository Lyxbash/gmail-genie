"""
Social network notification classification rules.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import SOCIAL_DOMAINS
from backend.rules.keyword_lists import SOCIAL_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY = "Social"


def classify_social(ctx: EmailContext) -> Optional[dict]:
    """Classify social platform activity and connection updates."""
    if domain_matches(ctx.domain, SOCIAL_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.95,
            reason="matched_social_domain",
        )

    if contains_any(ctx.combined, SOCIAL_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.91,
            reason="matched_social_keywords",
        )

    return None
