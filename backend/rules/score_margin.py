"""
Score margin utilities for ambiguous classification detection.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.rules.category_scoring import (
    apply_transactional_guards,
    compute_all_scores,
    newsletter_protection_boost,
)
from backend.rules.result_builder import EmailContext, prepare_email_context
from backend.rules.scoring import MIN_SCORE_THRESHOLD
from backend.rules.sender_learning import apply_sender_correction_boost

# Only margin 0–1 counts as ambiguous (was 2 — caused review spam).
LOW_MARGIN_THRESHOLD = 1
REVIEW_MARGIN_THRESHOLD = 1


def compute_score_margin(ctx: EmailContext) -> Dict[str, Any]:
    """
    Compare top two category scores after guards/boosts.

    Low margin (top - second <= LOW_MARGIN_THRESHOLD) indicates ambiguity.
    """
    scores = compute_all_scores(ctx)
    apply_transactional_guards(scores, ctx)
    newsletter_protection_boost(scores, ctx)
    apply_sender_correction_boost(scores, ctx)

    ranked = sorted(
        [(cs.category, cs.score) for cs in scores.values()],
        key=lambda x: x[1],
        reverse=True,
    )
    if not ranked:
        return {
            "top_category": None,
            "second_category": None,
            "top_score": 0,
            "second_score": 0,
            "score_margin": 0,
            "low_margin": True,
        }

    top_cat, top_score = ranked[0]
    second_cat, second_score = ranked[1] if len(ranked) > 1 else ("", 0)
    margin = top_score - second_score
    low_margin = margin <= LOW_MARGIN_THRESHOLD and top_score >= MIN_SCORE_THRESHOLD

    return {
        "top_category": top_cat,
        "second_category": second_cat,
        "top_score": top_score,
        "second_score": second_score,
        "score_margin": margin,
        "low_margin": low_margin,
    }


def compute_score_margin_for_email(
    sender: str,
    subject: str,
    snippet: str = "",
) -> Dict[str, Any]:
    ctx = prepare_email_context(sender, subject, snippet)
    return compute_score_margin(ctx)


def review_reason_from_signals(
    *,
    confidence: float,
    source: str,
    score_margin: Optional[int] = None,
    low_margin: bool = False,
    confidence_threshold: float = 0.70,
    rules_trusted: bool = False,
) -> Optional[str]:
    """Return review reason code or None if no review needed."""
    if rules_trusted:
        return None

    src = (source or "rules").lower()
    path = src
    if src in ("rules", "rules_direct", "rules_override"):
        if confidence >= 0.90:
            return None
    if src == "rules_verified" and confidence >= 0.85:
        return None
    if src == "semantic" and confidence >= 0.90:
        return None

    if confidence < confidence_threshold:
        return "low_confidence"
    if src == "groq_escalation":
        return "groq_escalation"
    if src == "semantic":
        return "semantic_fallback"
    if src == "rules_verified":
        return "semantic_verify"
    if low_margin or (
        score_margin is not None and score_margin <= REVIEW_MARGIN_THRESHOLD
    ):
        return "low_score_margin"
    return None


REVIEW_PRIORITY = {
    "groq_escalation": 0,
    "semantic_fallback": 1,
    "semantic_verify": 2,
    "low_confidence": 3,
    "low_score_margin": 4,
}


def review_priority(reason: str) -> int:
    return REVIEW_PRIORITY.get(reason, 99)
