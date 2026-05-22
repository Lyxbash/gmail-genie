"""
Fallback and personal-email classification rules.

Always returns a result — used as the terminal step in the pipeline.
"""

from __future__ import annotations

from backend.rules.keyword_lists import PERSONAL_KEYWORDS
from backend.rules.result_builder import EmailContext, build_result, contains_any

CATEGORY_GENERAL = "General"
CATEGORY_PERSONAL = "Personal"


def classify_fallback(ctx: EmailContext) -> dict:
    """
    Final classification when no higher-priority rule matched.

    Checks personal patterns before defaulting to General.
    """
    if contains_any(ctx.combined, PERSONAL_KEYWORDS):
        return build_result(
            category=CATEGORY_PERSONAL,
            confidence=0.85,
            reason="matched_personal_keywords",
        )

    return build_result(
        category=CATEGORY_GENERAL,
        confidence=0.40,
        reason="rule_fallback_no_match",
    )
