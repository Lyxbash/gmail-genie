"""
Per-category weighted signal scorers (intent-first, not domain-only).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.rules.domain_lists import (
    FINANCE_DOMAINS,
    JOB_DOMAINS,
    NEWSLETTER_DOMAINS,
    SHOPPING_DOMAINS,
    SOCIAL_DOMAINS,
    TRAVEL_DOMAINS,
)
from backend.rules.keyword_lists import (
    FINANCE_KEYWORDS,
    JOB_ALERT_KEYWORDS,
    JOB_APPLICATION_KEYWORDS,
    NEWSLETTER_KEYWORDS,
    PROMOTION_KEYWORDS,
    RECEIPT_KEYWORDS,
    RECRUITER_KEYWORDS,
    SECURITY_KEYWORDS,
    SHOPPING_KEYWORDS,
    SOCIAL_KEYWORDS,
    TRAVEL_KEYWORDS,
    WORK_KEYWORDS,
)
from backend.rules.result_builder import (
    EmailContext,
    contains_any,
    domain_matches,
    extract_sender_mailbox,
    hostname_matches_registry,
)
from backend.rules.scoring import (
    CategoryScore,
    DOMAIN_HINT_POINTS,
    JOB_SCORE_CATEGORIES,
    apply_keyword_signals,
    has_hiring_intent,
    has_transactional_block,
)

# Shared negative bundles
_TXN_NEG = [
    ("refund", 8),
    ("receipt", 8),
    ("invoice", 7),
    ("transaction", 6),
    ("subscription activated", 7),
    ("payment received", 6),
    ("otp", 8),
    ("verification code", 8),
]
_JOB_NEG = [
    ("digest", 5),
    ("newsletter", 5),
    ("roundup", 5),
    ("weekly digest", 6),
    ("refund", 8),
    ("invoice", 7),
    ("receipt", 8),
    ("subscription", 5),
    ("security alert", 7),
]
_NL_BOOST = [
    ("digest", 5),
    ("weekly", 4),
    ("daily", 4),
    ("roundup", 5),
    ("round-up", 5),
    ("edition", 4),
    ("newsletter", 5),
    ("issue #", 5),
    ("curated for you", 5),
    ("the batch", 6),
    ("weekly digest", 6),
    ("daily update", 5),
    ("morning brew", 4),
]
_PROMO_NEG = _NL_BOOST + [
    ("webinar", 6),
    ("masterclass", 5),
    ("coding digest", 6),
    ("tech roundup", 5),
    ("ai update", 5),
    ("the code", 4),
    ("interview prep", 6),
    ("career tips", 5),
]
_JOB_APP_NEG = _NL_BOOST + [
    ("interview prep", 8),
    ("career tips", 7),
    ("weekly contest", 6),
    ("coding challenge newsletter", 7),
]


def _domain_hint(cs: CategoryScore, ctx: EmailContext, domains: List[str]) -> None:
    if domain_matches(ctx.domain, domains):
        cs.add_positive(DOMAIN_HINT_POINTS, "domain_hint")


def score_security(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Security Alerts")
    apply_keyword_signals(cs, ctx.combined, [(k, 5) for k in SECURITY_KEYWORDS[:12]], [])
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("password reset", 6),
            ("verification code", 6),
            ("security alert", 5),
            ("otp", 6),
            ("sign-in", 4),
            ("login attempt", 5),
        ],
        _JOB_NEG,
    )
    if hostname_matches_registry(ctx.domain, ["accounts.google.com", "id.apple.com"]):
        cs.add_positive(4, "security_host")
    return cs


def score_receipts(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Receipts")
    apply_keyword_signals(
        cs,
        ctx.combined,
        [(k, 4) for k in RECEIPT_KEYWORDS[:15]],
        [("hiring", 6), ("recruiter", 6), ("digest", 5), ("newsletter", 5)],
    )
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("refund", 6),
            ("receipt", 6),
            ("invoice", 5),
            ("order confirmation", 5),
        ],
        [("you sent a payment", 8), ("payment sent", 7)],
    )
    local, host = extract_sender_mailbox(ctx.sender)
    if not local and "googleplay-noreply" in ctx.sender_lower:
        local = "googleplay-noreply"
    if local in ("googleplay-noreply",) or "receipt" in local or local == "invoice":
        cs.add_positive(8, "receipt_sender")
    if "googleplay-noreply" in ctx.sender_lower:
        cs.add_positive(10, "google_play_sender_override")
    if hostname_matches_registry(host, ["stripe.com", "paypal.com"]):
        if contains_any(ctx.subject_lower, ["receipt", "invoice", "refund", "payment"]):
            cs.add_positive(6, "payment_provider_txn")
    return cs


def score_finance(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Finance")
    _domain_hint(cs, ctx, FINANCE_DOMAINS)
    apply_keyword_signals(
        cs,
        ctx.combined,
        [(k, 4) for k in FINANCE_KEYWORDS],
        _NL_BOOST + [("hiring", 6), ("the batch", 8), ("deeplearning", 6)],
    )
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("subscription", 5),
            ("subscription activated", 6),
            ("billing", 5),
            ("bank statement", 6),
            ("mutual fund", 5),
            ("you sent a payment", 7),
            ("payment sent", 6),
        ],
        [("50% off", 6), ("limited time sale", 6), ("% off", 5)],
    )
    local, _ = extract_sender_mailbox(ctx.sender)
    if not local:
        if "googleone-noreply" in ctx.sender_lower:
            local = "googleone-noreply"
        elif "pay-noreply" in ctx.sender_lower:
            local = "pay-noreply"
    if local in ("googleone-noreply", "pay-noreply", "billing", "payments-noreply", "payments"):
        cs.add_positive(8, "finance_sender")
    if contains_any(
        ctx.subject_lower,
        ["activated", "subscription", "plan", "billing", "google one", "google ai"],
    ):
        cs.add_positive(6, "subscription_activation_subject")
    return cs


def score_shopping(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Shopping")
    _domain_hint(cs, ctx, SHOPPING_DOMAINS)
    apply_keyword_signals(
        cs,
        ctx.combined,
        [(k, 3) for k in SHOPPING_KEYWORDS[:12]],
        _JOB_NEG,
    )
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("shipped", 5),
            ("delivery", 4),
            ("order", 3),
            ("tracking", 5),
        ],
        [],
    )
    return cs


def score_travel(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Travel")
    _domain_hint(cs, ctx, TRAVEL_DOMAINS)
    apply_keyword_signals(cs, ctx.combined, [(k, 4) for k in TRAVEL_KEYWORDS[:14]], _JOB_NEG)
    return cs


def score_newsletters(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Newsletters")
    _domain_hint(cs, ctx, NEWSLETTER_DOMAINS)
    apply_keyword_signals(cs, ctx.combined, [(k, 3) for k in NEWSLETTER_KEYWORDS], _TXN_NEG)
    apply_keyword_signals(cs, ctx.subject_lower, _NL_BOOST, [("interview scheduled", 6)])
    apply_keyword_signals(
        cs,
        ctx.combined,
        [
            ("substack", 5),
            ("beehiiv", 5),
            ("tldr", 5),
            ("coursera", 3),
            ("udemy", 3),
            ("assignment due", 3),
        ],
        [],
    )
    local, host = extract_sender_mailbox(ctx.sender)
    if local == "newsletters-noreply":
        cs.add_positive(10, "linkedin_newsletters_sender")
    if host == "leetcode.com" and contains_any(
        ctx.subject_lower, ["digest", "weekly", "contest"]
    ):
        cs.add_positive(9, "leetcode_digest")
    if hostname_matches_registry(
        host,
        ["deeplearning.ai", "tldrnewsletter.com", "joinsuperhuman.ai", "codepen.io"],
    ):
        cs.add_positive(6, "newsletter_platform_host")
    if contains_any(ctx.combined, ["the batch", "superhuman", "the code"]):
        if contains_any(ctx.subject_lower, ["newsletter", "digest", "edition", "issue"]):
            cs.add_positive(7, "editorial_brand_digest")
    if "interview prep" in ctx.combined and "digest" in ctx.subject_lower:
        cs.add_negative(6, "interview_prep_not_job_app")
    return cs


def score_job_applications(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Job Applications/Referrals")
    if has_transactional_block(ctx.combined):
        cs.add_negative(15, "transactional_veto")
        return cs
    apply_keyword_signals(
        cs,
        ctx.combined,
        [(k, 4) for k in JOB_APPLICATION_KEYWORDS if k != "leetcode"],
        _JOB_APP_NEG + [("refund", 8), ("receipt", 8)],
    )
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("application received", 6),
            ("application status", 6),
            ("application submitted", 6),
            ("referral", 4),
            ("offer letter", 6),
        ],
        _JOB_APP_NEG + [("interview prep", 8)],
    )
    if contains_any(ctx.subject_lower, ["interview", "assessment"]):
        if not contains_any(
            ctx.subject_lower,
            ["digest", "newsletter", "weekly", "prep guide", "tips"],
        ):
            cs.add_positive(5, "hiring_pipeline_interview")
    return cs


def score_job_alerts(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Job Alerts")
    if has_transactional_block(ctx.combined):
        cs.add_negative(15, "transactional_veto")
        return cs
    hiring = has_hiring_intent(ctx.combined)
    if hiring and domain_matches(ctx.domain, JOB_DOMAINS):
        _domain_hint(cs, ctx, JOB_DOMAINS)
    apply_keyword_signals(
        cs,
        ctx.combined,
        [(k, 3) for k in JOB_ALERT_KEYWORDS],
        _JOB_NEG,
    )
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("hiring", 5),
            ("recruiter", 4),
            ("opportunity", 4),
            ("position", 3),
            ("opening", 4),
            ("apply now", 5),
            ("careers", 4),
        ],
        _JOB_NEG,
    )
    local, host = extract_sender_mailbox(ctx.sender)
    if local == "jobs-noreply":
        cs.add_positive(9, "linkedin_jobs_sender")
    if hostname_matches_registry(host, ["careers.google.com", "careers.microsoft.com"]):
        cs.add_positive(5, "careers_host")
    return cs


def score_recruiters(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Recruiters")
    if has_transactional_block(ctx.combined):
        cs.add_negative(15, "transactional_veto")
        return cs
    apply_keyword_signals(
        cs,
        ctx.combined,
        [(k, 4) for k in RECRUITER_KEYWORDS],
        _NL_BOOST + [("refund", 8)],
    )
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("quick chat", 6),
            ("senior engineer", 5),
            ("hiring manager", 5),
            ("recruiter", 4),
            ("role —", 4),
            ("role -", 4),
        ],
        _JOB_NEG,
    )
    local, host = extract_sender_mailbox(ctx.sender)
    if local in ("hiring", "recruiter", "talent") or local.startswith("recruiter"):
        cs.add_positive(7, "recruiter_mailbox")
    return cs


def score_social(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Social")
    _domain_hint(cs, ctx, SOCIAL_DOMAINS)
    apply_keyword_signals(cs, ctx.combined, [(k, 3) for k in SOCIAL_KEYWORDS], _TXN_NEG)
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("viewed your profile", 5),
            ("profile view", 5),
            ("connection request", 5),
            ("invited you to connect", 5),
            ("new message", 4),
            ("mentioned you", 4),
        ],
        _JOB_NEG,
    )
    local, host = extract_sender_mailbox(ctx.sender)
    if hostname_matches_registry(host, ["linkedin.com", "linkedinmail.com"]):
        if "messaging-digest" in local or local.startswith("invitations"):
            cs.add_positive(7, "linkedin_social_sender")
        if contains_any(
            ctx.subject_lower,
            ["account summary", "viewed your profile", "profile view"],
        ):
            cs.add_positive(6, "linkedin_activity_subject")
            cs.add_negative(6, "not_newsletter_digest")
    return cs


def score_promotions(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Promotions")
    if has_transactional_block(ctx.combined):
        cs.add_negative(12, "transactional_veto")
        return cs
    apply_keyword_signals(
        cs,
        ctx.combined,
        [(k, 3) for k in PROMOTION_KEYWORDS[:18]],
        _PROMO_NEG
        + [
            ("application received", 7),
            ("recruiter", 5),
            ("refund", 7),
            ("receipt", 7),
            ("meeting reminder", 7),
            ("zoom meeting", 7),
            ("calendar invite", 6),
        ],
    )
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("% off", 6),
            ("50% off", 7),
            ("limited time sale", 6),
            ("annual plan", 4),
            ("discount", 5),
            ("sale", 4),
        ],
        [],
    )
    return cs


def score_work(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Work")
    apply_keyword_signals(cs, ctx.combined, [(k, 3) for k in WORK_KEYWORDS[:14]], _NL_BOOST)
    apply_keyword_signals(
        cs,
        ctx.subject_lower,
        [
            ("zoom meeting", 6),
            ("meeting reminder", 5),
            ("calendar invitation", 5),
            ("scheduled meeting", 5),
            ("join zoom", 5),
        ],
        [],
    )
    if hostname_matches_registry(ctx.domain, ["zoom.us", "calendar.google.com"]):
        if contains_any(ctx.subject_lower, ["meeting", "reminder", "scheduled", "invite"]):
            cs.add_positive(6, "meeting_platform")
    local, host = extract_sender_mailbox(ctx.sender)
    if local == "support" and hostname_matches_registry(host, ["github.com"]):
        cs.add_positive(5, "github_support")
    return cs


def score_docs(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Docs")
    apply_keyword_signals(
        cs,
        ctx.combined,
        [
            ("shared a document", 5),
            ("shared a page", 6),
            ("shared with you", 5),
            ("google drive", 4),
            ("notion", 3),
            ("figma", 3),
            ("commented on", 4),
        ],
        _JOB_NEG,
    )
    if hostname_matches_registry(ctx.domain, ["makenotion.com", "notion.so"]):
        if contains_any(ctx.subject_lower, ["shared", "invited", "commented", "page"]):
            cs.add_positive(7, "notion_collab_host")
    local, host = extract_sender_mailbox(ctx.sender)
    if local == "notifications" and hostname_matches_registry(host, ["github.com"]):
        cs.add_positive(5, "github_notifications")
    return cs


def score_education(ctx: EmailContext) -> CategoryScore:
    cs = CategoryScore("Education")
    apply_keyword_signals(
        cs,
        ctx.combined,
        [
            ("assignment", 4),
            ("course", 3),
            ("lesson", 3),
            ("coursera", 4),
            ("udemy", 4),
            ("datacamp", 4),
            ("certificate", 3),
            ("webinar", 5),
            ("masterclass", 4),
            ("learning session", 4),
            ("masters' union", 6),
            ("masters union", 6),
            ("mckinsey", 4),
        ],
        _TXN_NEG + [("sale", 4), ("discount", 4), ("coupon", 4)],
    )
    if contains_any(ctx.subject_lower, ["webinar", "workshop", "bootcamp", "cohort"]):
        cs.add_positive(5, "educational_event_subject")
    return cs


def compute_all_scores(ctx: EmailContext) -> Dict[str, CategoryScore]:
    """Run all category scorers (cheap string scans only)."""
    scorers = [
        score_security,
        score_receipts,
        score_finance,
        score_shopping,
        score_travel,
        score_newsletters,
        score_job_applications,
        score_job_alerts,
        score_recruiters,
        score_social,
        score_promotions,
        score_work,
        score_docs,
        score_education,
    ]
    out: Dict[str, CategoryScore] = {}
    for fn in scorers:
        cs = fn(ctx)
        out[cs.category] = cs
    return out


def apply_transactional_guards(
    scores: Dict[str, CategoryScore], ctx: EmailContext
) -> None:
    """Collapse job scores when billing/refund/subscription signals are present."""
    if not has_transactional_block(ctx.combined):
        return
    for cat in JOB_SCORE_CATEGORIES:
        cs = scores.get(cat)
        if cs:
            cs.add_negative(12, "transactional_guard")


def newsletter_protection_boost(scores: Dict[str, CategoryScore], ctx: EmailContext) -> None:
    """Strong editorial/digest signals boost Newsletters; penalize Finance/Promotions/Jobs."""
    nl = scores.get("Newsletters")
    if not nl:
        return
    if has_transactional_block(ctx.combined):
        return
    strong = contains_any(ctx.subject_lower, [k for k, _ in _NL_BOOST]) or contains_any(
        ctx.combined,
        ["substack", "beehiiv", "tldr", "deeplearning.ai", "the batch", "newsletter@"],
    )
    if strong:
        nl.add_positive(5, "newsletter_protection_boost")
        for cat in ("Promotions", "Finance", "Job Alerts", "Job Applications/Referrals"):
            other = scores.get(cat)
            if other:
                other.add_negative(8, "newsletter_guard")
    if contains_any(ctx.subject_lower, ["account summary", "profile view", "viewed your profile"]):
        nl_score = scores.get("Newsletters")
        if nl_score:
            nl_score.add_negative(10, "account_activity_not_digest")
