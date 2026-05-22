"""
Government and civic service classification rules.

Maps to ``General`` (no Government category in config.yaml).
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import GOVERNMENT_DOMAINS
from backend.rules.keyword_lists import GOVERNMENT_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY = "General"


def classify_government(ctx: EmailContext) -> Optional[dict]:
    """Classify tax, ID, and public-sector notifications."""
    if domain_matches(ctx.domain, GOVERNMENT_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.94,
            reason="matched_government_domain",
        )

    if contains_any(ctx.combined, GOVERNMENT_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.91,
            reason="matched_government_keywords",
        )

    return None
