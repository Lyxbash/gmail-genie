"""
Intent-first rule classification via weighted signal scoring.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from backend.rules.category_scoring import (
    apply_transactional_guards,
    compute_all_scores,
    newsletter_protection_boost,
)
from backend.rules.sender_learning import apply_sender_correction_boost
from backend.rules.result_builder import EmailContext, build_result
from backend.rules.rule_trace import RuleTrace
from backend.rules.scoring import (
    DOMAIN_ONLY_MAX_CONFIDENCE,
    JOB_DOMAIN_ONLY_MAX_CONFIDENCE,
    JOB_SCORE_CATEGORIES,
    MIN_SCORE_THRESHOLD,
    CategoryScore,
    is_domain_only_match,
    score_to_confidence,
)

# Tie-break priority (transactional / safety first)
_TIE_PRIORITY: List[str] = [
    "Security Alerts",
    "Receipts",
    "Finance",
    "Shopping",
    "Travel",
    "Newsletters",
    "Job Applications/Referrals",
    "Job Alerts",
    "Recruiters",
    "Social",
    "Docs",
    "Work",
    "Education",
    "Promotions",
    "General",
]


def debug_scored_breakdown(ctx: EmailContext) -> Dict[str, object]:
    """Full score table for debug-classify (no side effects)."""
    from backend.rules.category_scoring import (
        apply_transactional_guards,
        compute_all_scores,
        newsletter_protection_boost,
    )

    scores = compute_all_scores(ctx)
    apply_transactional_guards(scores, ctx)
    newsletter_protection_boost(scores, ctx)
    apply_sender_correction_boost(scores, ctx)

    vetoes: List[str] = []
    positive_scores: Dict[str, List[str]] = {}
    negative_scores: Dict[str, List[str]] = {}
    category_scores: Dict[str, int] = {}

    for cat, cs in scores.items():
        category_scores[cat] = cs.score
        if cs.positive_signals:
            positive_scores[cat] = list(cs.positive_signals)
        if cs.negative_signals:
            negative_scores[cat] = list(cs.negative_signals)
            for sig in cs.negative_signals:
                if "veto" in sig or "guard" in sig:
                    vetoes.append(f"{cat}:{sig}")

    picked = _pick_winner(scores)
    winner_dict: Optional[Dict[str, object]] = None
    if picked:
        winner, specialized = picked
        conf = score_to_confidence(winner.score, specialized_sender=specialized)
        if is_domain_only_match(winner) and not specialized:
            cap = (
                JOB_DOMAIN_ONLY_MAX_CONFIDENCE
                if winner.category in JOB_SCORE_CATEGORIES
                else DOMAIN_ONLY_MAX_CONFIDENCE
            )
            conf = min(conf, cap)
        winner_dict = {
            "category": winner.category,
            "confidence": conf,
            "score": winner.score,
            "reason": f"scored_{winner.category}_score{winner.score}",
        }

    margin_info: Dict[str, object] = {}
    if category_scores:
        ranked = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        top_cat, top_sc = ranked[0]
        second_cat, second_sc = ranked[1] if len(ranked) > 1 else ("", 0)
        margin = top_sc - second_sc
        margin_info = {
            "top_category": top_cat,
            "second_category": second_cat,
            "top_score": top_sc,
            "second_score": second_sc,
            "score_margin": margin,
            "low_margin": margin <= 2 and top_sc >= MIN_SCORE_THRESHOLD,
        }

    return {
        "positive_scores": positive_scores,
        "negative_scores": negative_scores,
        "category_scores": category_scores,
        "vetoes": vetoes,
        "winner": winner_dict,
        **margin_info,
    }


def _pick_winner(scores: Dict[str, CategoryScore]) -> Optional[Tuple[CategoryScore, bool]]:
    """Return (best CategoryScore, specialized_sender_flag) or None."""
    candidates = [
        cs for cs in scores.values() if cs.score >= MIN_SCORE_THRESHOLD
    ]
    if not candidates:
        return None

    max_score = max(cs.score for cs in candidates)
    top = [cs for cs in candidates if cs.score == max_score]

    if len(top) == 1:
        winner = top[0]
    else:
        winner = sorted(
            top,
            key=lambda cs: _TIE_PRIORITY.index(cs.category)
            if cs.category in _TIE_PRIORITY
            else 99,
        )[0]

    specialized = any(
        s in winner.positive_signals
        for s in (
            "linkedin_newsletters_sender",
            "linkedin_jobs_sender",
            "leetcode_digest",
            "receipt_sender",
            "finance_sender",
            "linkedin_social_sender",
            "careers_host",
            "payment_provider_txn",
            "google_play_sender_override",
            "subscription_activation_subject",
        )
    )
    return winner, specialized


def classify_scored_rules(
    ctx: EmailContext,
    trace: Optional[RuleTrace] = None,
) -> Optional[dict]:
    """
    Classify using weighted signals across categories.

    Returns None when no category clears the score threshold.
    """
    scores = compute_all_scores(ctx)
    apply_transactional_guards(scores, ctx)
    newsletter_protection_boost(scores, ctx)
    apply_sender_correction_boost(scores, ctx)

    if trace is not None:
        trace.record_scores(scores)

    picked = _pick_winner(scores)
    if not picked:
        return None

    winner, specialized = picked
    conf = score_to_confidence(winner.score, specialized_sender=specialized)

    if is_domain_only_match(winner) and not specialized:
        cap = (
            JOB_DOMAIN_ONLY_MAX_CONFIDENCE
            if winner.category in JOB_SCORE_CATEGORIES
            else DOMAIN_ONLY_MAX_CONFIDENCE
        )
        conf = min(conf, cap)

    reason = (
        f"scored_{winner.category.lower().replace('/', '_')}"
        f"_score{winner.score}"
        f"_pos={','.join(winner.positive_signals[:4])}"
    )
    return build_result(
        category=winner.category,
        confidence=conf,
        reason=reason[:120],
    )
