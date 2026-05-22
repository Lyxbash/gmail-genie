"""
Finance, banking, and utility-bill classification rules.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import BILL_DOMAINS, FINANCE_DOMAINS
from backend.rules.keyword_lists import BILL_UTILITY_KEYWORDS, FINANCE_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY = "Finance"

NEWSLETTER_NEGATIVE_GUARDS = [
    "newsletter",
    "digest",
    "weekly digest",
    "daily digest",
    "roundup",
    "edition",
    "the batch",
]

SENDER_FINANCE_OVERRIDES = [
    "googleone-noreply@google.com",
    "payments-noreply@google.com",
    "payments@google.com",
]


def classify_finance(ctx: EmailContext) -> Optional[dict]:
    """Classify banking, fintech, investments, and utility bills."""
    # Sender specializations — avoid broad-domain collisions.
    if any(s in ctx.sender_lower for s in SENDER_FINANCE_OVERRIDES):
        if contains_any(
            ctx.subject_lower,
            ["subscription", "refund", "payment", "invoice", "receipt", "charged", "billing"],
        ):
            return build_result(
                category=CATEGORY,
                confidence=0.97,
                reason="sender_finance_override",
            )

    if domain_matches(ctx.domain, FINANCE_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.91,
            reason="matched_finance_domain",
        )

    # Negative guard: newsletter/digest content should not map to Finance unless
    # it comes from a known finance/billing domain (checked above/below).
    if contains_any(ctx.subject_lower, NEWSLETTER_NEGATIVE_GUARDS):
        return None

    if contains_any(ctx.combined, FINANCE_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.93,
            reason="matched_finance_keywords",
        )

    if domain_matches(ctx.domain, BILL_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.89,
            reason="matched_utility_bill_domain",
        )

    if contains_any(ctx.combined, BILL_UTILITY_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.91,
            reason="matched_utility_bill_keywords",
        )

    return None
