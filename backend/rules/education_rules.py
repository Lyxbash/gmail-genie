"""
Education and online learning classification rules.

Maps to ``General`` (no Education category in config.yaml).
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import EDUCATION_DOMAINS
from backend.rules.keyword_lists import EDUCATION_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY = "General"


def classify_education(ctx: EmailContext) -> Optional[dict]:
    """Classify courses, assignments, and learning platforms."""
    if domain_matches(ctx.domain, EDUCATION_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.91,
            reason="matched_education_domain",
        )

    if contains_any(ctx.combined, EDUCATION_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.88,
            reason="matched_education_keywords",
        )

    return None
