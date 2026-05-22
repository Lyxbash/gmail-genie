"""
High-specificity sender/host rules for major brands.

Runs after Security/Spam — always before weighted scoring.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    extract_sender_mailbox,
    hostname_matches_registry,
)


def classify_entity_special(ctx: EmailContext) -> Optional[dict]:
    """Exact sender/host specializations (0.97–0.99 confidence)."""
    local, host = extract_sender_mailbox(ctx.sender)

    # ------------------------------------------------------------------ Google
    sl = ctx.sender_lower
    if host == "google.com" or "google.com" in sl:
        if local in ("googleplay-noreply",) or "googleplay-noreply@" in sl:
            return build_result("Receipts", 0.99, "google_play_transactional_sender")
        if local in ("googleone-noreply", "pay-noreply") or "googleone-noreply@" in sl or "pay-noreply@" in sl:
            return build_result("Finance", 0.98, "google_one_or_pay_sender")
        if local in ("payments-noreply", "payment-noreply", "payments"):
            return build_result("Finance", 0.98, "google_payments_sender")
        if local in ("security-noreply",):
            return build_result("Security Alerts", 0.98, "google_security_sender")
        if local in ("no-reply", "noreply", "no_reply"):
            if contains_any(
                ctx.subject_lower,
                [
                    "finish setting up",
                    "set up your",
                    "new device",
                    "device added",
                    "welcome",
                    "account setup",
                    "account summary",
                ],
            ) and not contains_any(
                ctx.subject_lower,
                ["verification code", "otp", "password", "security alert"],
            ):
                return build_result(
                    "General",
                    0.94,
                    "google_setup_or_summary_noreply",
                )
            if contains_any(
                ctx.subject_lower,
                ["recovery", "verify your", "confirm your"],
            ):
                return build_result(
                    "Security Alerts",
                    0.92,
                    "google_security_noreply_subject",
                )
            return build_result("General", 0.72, "google_generic_noreply")

    if host == "accounts.google.com":
        return build_result("Security Alerts", 0.99, "google_accounts_host")

    if host == "careers.google.com":
        return build_result("Job Alerts", 0.96, "google_careers_host")

    # ------------------------------------------------------------------ Amazon
    if hostname_matches_registry(host, ["amazon.com", "amazon.in", "amazon.co.uk"]):
        if local.startswith("shipment") or "ship" in local:
            return build_result("Shopping", 0.95, "amazon_shipping_sender")
        if local.startswith("receipts") or local == "receipts":
            return build_result("Receipts", 0.97, "amazon_receipts_sender")
        if local.startswith("payments") or "payments" in local:
            return build_result("Finance", 0.95, "amazon_payments_sender")
        if "jobs" in local or local == "careers":
            return build_result("Job Alerts", 0.94, "amazon_jobs_sender")

    # ------------------------------------------------------------------ Microsoft
    if hostname_matches_registry(host, ["microsoft.com"]) or host.endswith(
        ".microsoft.com"
    ):
        if "account-security" in local:
            return build_result(
                "Security Alerts", 0.97, "microsoft_account_security_sender"
            )
        if local == "invoice":
            return build_result("Receipts", 0.96, "microsoft_invoice_sender")
        if "careers" in host:
            return build_result("Job Alerts", 0.94, "microsoft_careers_sender")

    # ------------------------------------------------------------------ Apple
    if host == "id.apple.com" or local == "appleid":
        return build_result("Security Alerts", 0.97, "apple_id_sender")
    if host.endswith("apple.com"):
        if local == "subscriptions":
            return build_result("Finance", 0.96, "apple_subscriptions_sender")
        if local == "receipts":
            return build_result("Receipts", 0.97, "apple_receipts_sender")

    # ------------------------------------------------------------------ Stripe / PayPal
    if hostname_matches_registry(host, ["stripe.com"]):
        if local == "billing" or "billing" in local:
            return build_result("Finance", 0.97, "stripe_billing_sender")
        if contains_any(ctx.subject_lower, ["receipt", "invoice", "refund", "payment"]):
            return build_result("Receipts", 0.94, "stripe_transactional_subject")
    if hostname_matches_registry(host, ["paypal.com"]):
        if contains_any(
            ctx.subject_lower, ["you sent a payment", "payment sent", "money sent"]
        ):
            return build_result("Finance", 0.96, "paypal_payment_sent_subject")
        if contains_any(ctx.subject_lower, ["receipt", "invoice", "refund"]):
            return build_result("Receipts", 0.94, "paypal_transactional_subject")

    if hostname_matches_registry(host, ["shopify.com"]):
        if contains_any(
            ctx.subject_lower,
            ["% off", "sale", "discount", "limited time", "promo", "coupon"],
        ):
            return build_result("Promotions", 0.94, "shopify_promo_subject")

    # ------------------------------------------------------------------ Naukri / job boards
    if hostname_matches_registry(host, ["naukri.com", "naukri.mail", "indeed.com"]):
        if contains_any(
            ctx.subject_lower,
            ["job alert", "recommended jobs", "matching jobs", "new jobs"],
        ) or local in ("alert", "alerts", "jobs", "noreply"):
            return build_result("Job Alerts", 0.96, "naukri_job_alert_sender")

    # ------------------------------------------------------------------ LinkedIn
    if hostname_matches_registry(host, ["linkedin.com", "linkedinmail.com"]):
        if local == "newsletters-noreply":
            return build_result("Newsletters", 0.99, "linkedin_newsletters_sender")
        if local == "jobs-noreply":
            return build_result("Job Alerts", 0.96, "linkedin_jobs_noreply")
        if local.startswith("invitations") or local == "invitations":
            return build_result("Social", 0.93, "linkedin_invitations_sender")
        if "messaging-digest" in local:
            return build_result("Social", 0.90, "linkedin_messaging_digest_sender")
        if local in ("noreply", "no-reply") and contains_any(
            ctx.subject_lower,
            ["account summary", "profile view", "viewed your profile"],
        ):
            return build_result("Social", 0.93, "linkedin_account_activity_noreply")

    # ------------------------------------------------------------------ LeetCode
    if host == "leetcode.com":
        if contains_any(ctx.subject_lower, ["digest", "weekly", "contest", "interview prep"]):
            return build_result("Newsletters", 0.96, "leetcode_digest_sender")

    # ------------------------------------------------------------------ GitHub
    if hostname_matches_registry(host, ["github.com"]):
        if local == "billing":
            return build_result("Finance", 0.95, "github_billing_sender")
        if "security" in local or "security" in ctx.subject_lower:
            return build_result("Security Alerts", 0.94, "github_security_sender")
        if local == "notifications":
            return build_result("Docs", 0.78, "github_notifications_sender")
        if local == "support":
            return build_result("Work", 0.80, "github_support_sender")

    # ------------------------------------------------------------------ DeepLearning.AI / TLDR
    if hostname_matches_registry(
        host,
        ["deeplearning.ai", "tldrnewsletter.com", "beehiiv.com", "substack.com"],
    ):
        if contains_any(ctx.subject_lower, ["the batch", "newsletter", "digest"]):
            return build_result("Newsletters", 0.95, "editorial_platform_sender")

    return None
