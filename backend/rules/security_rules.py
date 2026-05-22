"""
Security and account-alert classification rules.

Highest priority in the rule pipeline — OTP, login alerts, password resets.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import SECURITY_DOMAINS
from backend.rules.keyword_lists import (
    SECURITY_DOMAIN_SUBJECT_KEYWORDS,
    SECURITY_KEYWORDS,
    SECURITY_SUBJECT_KEYWORDS,
)
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
    hostname_matches_registry,
)

CATEGORY = "Security Alerts"


def classify_security(ctx: EmailContext) -> Optional[dict]:
    """
    Classify security-sensitive emails.

    Returns a structured result dict or None if no security signal matches.
    """
    if hostname_matches_registry(ctx.domain, ["accounts.google.com"]):
        return build_result(
            category=CATEGORY,
            confidence=0.98,
            reason="google_account_security_host",
        )

    if contains_any(ctx.combined, SECURITY_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.96,
            reason="matched_security_keywords",
        )

    if contains_any(ctx.subject_lower, SECURITY_SUBJECT_KEYWORDS):
        return build_result(
            category=CATEGORY,
            confidence=0.95,
            reason="matched_security_subject",
        )

    if domain_matches(ctx.domain, SECURITY_DOMAINS):
        if contains_any(ctx.subject_lower, SECURITY_DOMAIN_SUBJECT_KEYWORDS):
            return build_result(
                category=CATEGORY,
                confidence=0.85,
                reason="security_domain_with_alert_subject",
            )

    return None
