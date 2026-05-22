"""
Rule trust calibration — when to skip LLM verification and trust rules directly.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.config import load_config

_llm = load_config().get("llm", {})

RULE_TRUST_SHORT_CIRCUIT = float(_llm.get("rule_trust_short_circuit", 0.93))
RULE_VERIFY_MIN_CONFIDENCE = float(_llm.get("rule_verify_min_confidence", 0.72))
RULE_VERIFY_MAX_CONFIDENCE = float(_llm.get("rule_verify_max_confidence", 0.82))

# Strong entity / platform / sender reason markers (substring match on reason).
TRUSTED_REASON_MARKERS = (
    "google_play",
    "google_one",
    "google_security",
    "google_accounts",
    "linkedin_jobs",
    "linkedin_newsletters",
    "linkedin_invitations",
    "linkedin_social",
    "linkedin_account",
    "stripe_",
    "paypal_",
    "shopify_promo",
    "editorial_platform",
    "leetcode_digest",
    "receipt_sender",
    "finance_sender",
    "security_host",
    "matched_security",
    "amazon_receipts",
    "amazon_shipping",
    "notion_collab",
    "recruiter_mailbox",
    "careers_host",
    "payment_provider",
    "subscription_activation",
    "microsoft_account_security",
    "github_security",
)

# Scored winner with clear platform sender signals in positive_signals.
TRUSTED_SCORE_SIGNALS = (
    "linkedin_jobs_sender",
    "linkedin_newsletters_sender",
    "linkedin_social_sender",
    "google_play_sender_override",
    "receipt_sender",
    "finance_sender",
    "notion_collab_host",
    "recruiter_mailbox",
    "meeting_platform",
)


def is_strong_rule_match(rules: Dict[str, Any]) -> bool:
    """Obvious deterministic match — skip verification and promote trust."""
    conf = float(rules.get("confidence", 0))
    reason = (rules.get("reason") or "").lower()
    if conf >= RULE_TRUST_SHORT_CIRCUIT:
        return True
    if conf >= 0.88 and any(m in reason for m in TRUSTED_REASON_MARKERS):
        return True
    if conf >= 0.85 and any(
        s in reason for s in ("_sender", "special", "entity", "scored_")
    ):
        return True
    return False


def promote_rule_confidence(rules: Dict[str, Any]) -> Dict[str, Any]:
    """Boost borderline strong matches into high-trust band."""
    if not is_strong_rule_match(rules):
        return rules
    out = dict(rules)
    conf = float(out.get("confidence", 0))
    if conf < RULE_TRUST_SHORT_CIRCUIT:
        out["confidence"] = min(0.98, max(conf, 0.96))
        out["reason"] = (out.get("reason") or "") + ";trust_promoted"
    return out


def should_skip_rule_verify(
    rules: Dict[str, Any],
    margin_info: Dict[str, Any],
) -> bool:
    """Do not run Ollama yes/no verification for this rules result."""
    if is_strong_rule_match(rules):
        return True

    conf = float(rules.get("confidence", 0))
    margin = int(margin_info.get("score_margin", 0))
    top_score = int(margin_info.get("top_score", 0))
    top_cat = margin_info.get("top_category")
    rule_cat = rules.get("category")

    # Clear winner: large margin and decent score.
    if margin >= 4 and top_score >= 7 and conf >= 0.78:
        return True
    if rule_cat == top_cat and margin >= 3 and conf >= 0.80:
        return True
    if conf >= 0.90:
        return True
    return False


def should_use_rule_verify(
    rules: Dict[str, Any],
    margin_info: Dict[str, Any],
    *,
    verify_enabled: bool,
) -> bool:
    """
    Run LLM verification only for genuinely ambiguous rule outcomes.
    """
    if not verify_enabled:
        return False
    if should_skip_rule_verify(rules, margin_info):
        return False

    conf = float(rules.get("confidence", 0))
    if conf < RULE_VERIFY_MIN_CONFIDENCE or conf > RULE_VERIFY_MAX_CONFIDENCE:
        return False

    margin = int(margin_info.get("score_margin", 99))
    rule_cat = rules.get("category")
    top_cat = margin_info.get("top_category")

    # Borderline confidence band.
    if conf < 0.76:
        return True
    # Tight race between top categories.
    if margin <= 1 and top_score >= 5:
        return True
    # Rule category disagrees with score winner.
    if rule_cat and top_cat and rule_cat != top_cat and conf < 0.85:
        return True
    return False


def normalize_classification_path(source: str) -> str:
    """Map raw source to operational path label."""
    src = (source or "rules").lower()
    if src in ("rules", "rules_direct"):
        return "rules_direct"
    if src == "rules_verified":
        return "rules_verified"
    if src == "semantic":
        return "semantic_fallback"
    if src == "groq_escalation":
        return "groq_escalation"
    if src in ("rules_override",):
        return "rules_direct"
    if src in ("fallback",):
        return "fallback"
    return src
