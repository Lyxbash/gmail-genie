"""
Legacy boolean newsletter rules — NOT used by rule_engine.py.

Active pipeline: entity_special_rules → scored_rules (category_scoring.py).
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import NEWSLETTER_DOMAINS
from backend.rules.keyword_lists import NEWSLETTER_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
    extract_sender_mailbox,
)

CATEGORY = "Newsletters"

HIGH_PRIORITY_SENDERS = [
    "newsletters-noreply@linkedin.com",
]

HIGH_PRIORITY_SUBJECT_HINTS = [
    "newsletter",
    "digest",
    "weekly",
    "daily",
    "roundup",
    "round-up",
    "edition",
    "the batch",
    "product hunt daily",
    "product hunt weekly",
]

# Do not label payment/shipping/system mail as newsletters.
TRANSACTIONAL_LOCAL_HINTS = (
    "googleplay",
    "googleone",
    "payments",
    "payment",
    "invoice",
    "billing",
    "receipt",
    "shipping",
    "track",
    "stripe",
    "paypal",
)


def _is_transactional_sender(ctx: EmailContext) -> bool:
    local, _host = extract_sender_mailbox(ctx.sender)
    if not local:
        return False
    return any(h in local for h in TRANSACTIONAL_LOCAL_HINTS)


def classify_newsletters(ctx: EmailContext) -> Optional[dict]:
    """Classify subscriptions, digests, and editorial updates."""
    if _is_transactional_sender(ctx):
        return None

    if any(sender in ctx.sender_lower for sender in HIGH_PRIORITY_SENDERS):
        return build_result(
            category=CATEGORY,
            confidence=0.99,
            reason="linkedin_newsletters_sender",
        )

    if "leetcode" in ctx.sender_lower or ctx.domain == "leetcode.com":
        if contains_any(
            ctx.subject_lower,
            ["digest", "weekly", "contest", "interview prep"],
        ):
            return build_result(
                category=CATEGORY,
                confidence=0.94,
                reason="leetcode_digest_newsletter",
            )

    if domain_matches(ctx.domain, NEWSLETTER_DOMAINS):
        return build_result(
            category=CATEGORY,
            confidence=0.90,
            reason="matched_newsletter_domain",
        )

    if contains_any(ctx.subject_lower, HIGH_PRIORITY_SUBJECT_HINTS):
        return build_result(
            category=CATEGORY,
            confidence=0.88,
            reason="matched_newsletter_subject_hints",
        )

    if contains_any(ctx.combined, NEWSLETTER_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.82,
            reason="matched_newsletter_keywords",
        )

    return None
