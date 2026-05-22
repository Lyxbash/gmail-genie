"""
Spam and phishing classification rules.

Maps to ``General`` because config.yaml has no Spam category; reason
preserves intent for AI verification and future category expansion.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.keyword_lists import SPAM_COMBO_PATTERNS, SPAM_KEYWORDS
from backend.rules.result_builder import EmailContext, build_result, contains_any

# No dedicated Spam label in config.yaml — use General with explicit reason.
CATEGORY = "General"


def classify_spam(ctx: EmailContext) -> Optional[dict]:
    """Detect spam/phishing patterns before transactional rules run."""
    if contains_any(ctx.combined, SPAM_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.93,
            reason="matched_spam_keywords",
        )

    for pattern in SPAM_COMBO_PATTERNS:
        if all(fragment in ctx.combined for fragment in pattern):
            return build_result(
                category=CATEGORY,
                confidence=0.92,
                reason="matched_spam_combo_pattern",
            )

    return None
