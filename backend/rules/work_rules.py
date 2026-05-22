"""
Work and professional productivity classification rules.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import WORK_DOMAINS
from backend.rules.keyword_lists import WORK_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY = "Work"


def classify_work(ctx: EmailContext) -> Optional[dict]:
    """Classify SaaS tooling, meetings, and project communication."""
    if domain_matches(ctx.domain, WORK_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.95,
            reason="matched_work_domain",
        )

    if contains_any(ctx.combined, WORK_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.91,
            reason="matched_work_keywords",
        )

    return None
