"""
Legacy boolean job rules — NOT used by rule_engine.py.

Active pipeline: entity_special_rules → scored_rules (category_scoring.py).
Kept for reference during weighted-scoring migration.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import JOB_APPLICATION_SENDER_SUFFIXES, JOB_DOMAINS
from backend.rules.keyword_lists import (
    JOB_ALERT_KEYWORDS,
    JOB_APPLICATION_KEYWORDS,
    RECRUITER_KEYWORDS,
)
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    contains_word_any,
    domain_matches,
    extract_sender_mailbox,
    hostname_matches_registry,
)
from backend.rules.scoring import has_hiring_intent, has_transactional_block

CATEGORY_APPLICATION = "Job Applications/Referrals"
CATEGORY_ALERTS = "Job Alerts"
CATEGORY_RECRUITERS = "Recruiters"

BROAD_DOMAIN_CAP = 0.78

NEGATIVE_SUBJECT_NON_JOB = [
    "refund",
    "receipt",
    "invoice",
    "subscription",
    "payment",
    "activated plan",
    "billing",
    "security alert",
    "otp",
    "verification code",
    "your order",
    "shipped",
    "delivery",
]

NEGATIVE_SENDER_NON_JOB = [
    "googleplay",
    "googleone",
    "paypal",
    "stripe",
    "invoice",
    "billing",
    "receipt",
    "payments-noreply",
]

JOB_INTENT_KEYWORDS = [
    "job",
    "jobs",
    "hiring",
    "recruiter",
    "interview",
    "opportunity",
    "position",
    "opening",
    "career",
    "careers",
    "applied",
    "application received",
    "job alert",
    "referral",
]


def _is_negative_non_job(ctx: EmailContext) -> bool:
    if contains_any(ctx.subject_lower, NEGATIVE_SUBJECT_NON_JOB):
        return True
    if contains_any(ctx.sender_lower, NEGATIVE_SENDER_NON_JOB):
        return True
    return False


def _is_job_application(ctx: EmailContext) -> Optional[dict]:
    if _is_negative_non_job(ctx):
        return None

    if contains_any(
        ctx.subject_lower,
        ["newsletter", "digest", "weekly digest", "daily digest", "roundup"],
    ):
        return None

    for suffix in JOB_APPLICATION_SENDER_SUFFIXES:
        if ctx.sender_lower.endswith(suffix):
            return build_result(
                category=CATEGORY_APPLICATION,
                confidence=0.97,
                reason="careers_sender_suffix",
            )

    if contains_any(ctx.subject_lower, JOB_APPLICATION_KEYWORDS):
        return build_result(
            category=CATEGORY_APPLICATION,
            confidence=0.94,
            reason="matched_job_application_subject",
        )

    application_combined_signals = [
        "online assessment",
        "hackerrank",
        "codesignal",
        "codility",
        "next interview round",
    ]
    if contains_any(ctx.combined, application_combined_signals):
        return build_result(
            category=CATEGORY_APPLICATION,
            confidence=0.93,
            reason="matched_application_pipeline_keywords",
        )

    if "interview" in ctx.subject_lower and "job alert" not in ctx.subject_lower:
        return build_result(
            category=CATEGORY_APPLICATION,
            confidence=0.88,
            reason="interview_in_subject",
        )

    if "application status" in ctx.subject_lower:
        return build_result(
            category=CATEGORY_APPLICATION,
            confidence=0.94,
            reason="application_status_subject",
        )

    return None


def _is_job_alert(ctx: EmailContext) -> Optional[dict]:
    local, host = extract_sender_mailbox(ctx.sender)
    if local == "newsletters-noreply":
        return None

    if _is_negative_non_job(ctx):
        return None

    if contains_any(
        ctx.subject_lower,
        ["newsletter", "digest", "weekly digest", "daily digest", "roundup"],
    ):
        return None

    if hostname_matches_registry(host, ["linkedin.com", "linkedinmail.com"]):
        if "application was sent" in ctx.subject_lower:
            return build_result(
                category=CATEGORY_APPLICATION,
                confidence=0.94,
                reason="linkedin_application_sent",
            )
        if local == "jobs-noreply":
            return build_result(
                category=CATEGORY_ALERTS,
                confidence=0.96,
                reason="linkedin_jobs_noreply",
            )
        if contains_any(ctx.subject_lower, ["jobs", "job", "position", "opening"]):
            return build_result(
                category=CATEGORY_ALERTS,
                confidence=0.90,
                reason="linkedin_job_intent_subject",
            )

    if has_transactional_block(ctx.combined):
        return None

    if contains_any(ctx.combined, JOB_ALERT_KEYWORDS):
        return build_result(
            category=CATEGORY_ALERTS,
            confidence=0.88,
            reason="matched_job_alert_keywords",
        )

    portal_hints = [
        "haystack.cv",
        "unstop.news",
        "naukri",
        "indeed",
        "wellfound",
        "monster",
    ]
    if contains_any(ctx.combined, portal_hints):
        return build_result(
            CATEGORY_ALERTS,
            BROAD_DOMAIN_CAP - 0.02,
            "matched_job_portal_hint",
        )

    if has_transactional_block(ctx.combined):
        return None

    if domain_matches(ctx.domain, JOB_DOMAINS):
        if any(ctx.sender_lower.endswith(s) for s in JOB_APPLICATION_SENDER_SUFFIXES):
            return None
        if has_hiring_intent(ctx.combined):
            return build_result(
                category=CATEGORY_ALERTS,
                confidence=BROAD_DOMAIN_CAP,
                reason="matched_job_domain_with_intent",
            )

    return None


def _is_recruiter(ctx: EmailContext) -> Optional[dict]:
    if _is_negative_non_job(ctx):
        return None
    if contains_any(ctx.combined, RECRUITER_KEYWORDS):
        return build_result(
            category=CATEGORY_RECRUITERS,
            confidence=0.82,
            reason="matched_recruiter_keywords",
        )
    return None


def classify_jobs(ctx: EmailContext) -> Optional[dict]:
    result = _is_job_application(ctx)
    if result:
        return result

    result = _is_job_alert(ctx)
    if result:
        return result

    return _is_recruiter(ctx)
