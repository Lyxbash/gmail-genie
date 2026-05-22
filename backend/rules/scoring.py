"""
Lightweight weighted signal scoring for Gmail Genie rules.

Intent-first: domains add weak hints; keywords and senders drive classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


MIN_SCORE_THRESHOLD = 5
DOMAIN_HINT_POINTS = 2
DOMAIN_ONLY_MAX_CONFIDENCE = 0.65
JOB_DOMAIN_ONLY_MAX_CONFIDENCE = 0.55

TRANSACTIONAL_BLOCK_KEYWORDS = [
    "refund",
    "transaction",
    "receipt",
    "invoice",
    "subscription",
    "payment",
    "order",
    "charged",
    "credited",
    "debited",
    "billing",
    "google play",
    "google one",
]

HIRING_INTENT_KEYWORDS = [
    "hiring",
    "recruiter",
    "role",
    "opening",
    "interview",
    "application received",
    "application status",
    "position",
    "apply now",
    "opportunity",
    "careers",
    "job alert",
    "job alerts",
    "recommended jobs",
    "jobs for you",
]

JOB_SCORE_CATEGORIES = frozenset(
    {"Job Alerts", "Job Applications/Referrals", "Recruiters"}
)


@dataclass
class CategoryScore:
    category: str
    score: int = 0
    positive_signals: List[str] = field(default_factory=list)
    negative_signals: List[str] = field(default_factory=list)

    def add_positive(self, points: int, signal: str) -> None:
        self.score += points
        self.positive_signals.append(signal)

    def add_negative(self, points: int, signal: str) -> None:
        self.score -= points
        self.negative_signals.append(signal)


def score_to_confidence(score: int, *, specialized_sender: bool = False) -> float:
    """Map aggregate score to calibrated confidence."""
    if specialized_sender:
        return 0.98
    if score <= 2:
        return 0.40
    if score <= 5:
        return 0.65
    if score <= 8:
        return 0.88
    return min(0.97, 0.92 + (score - 9) * 0.01)


def apply_keyword_signals(
    cs: CategoryScore,
    text: str,
    positive: List[Tuple[str, int]],
    negative: List[Tuple[str, int]],
) -> None:
    """Apply (keyword, points) lists to a CategoryScore."""
    for kw, pts in positive:
        if kw in text:
            cs.add_positive(pts, kw)
    for kw, pts in negative:
        if kw in text:
            cs.add_negative(pts, kw)


def is_domain_only_match(cs: CategoryScore) -> bool:
    """True when classification relies almost entirely on a weak domain hint."""
    if cs.score > 3:
        return False
    positives = set(cs.positive_signals)
    return positives <= {"domain_hint"} or (
        len(positives) == 1 and "domain_hint" in positives
    )


def has_transactional_block(text: str) -> bool:
    """Billing/refund/subscription signals — job categories must not win."""
    from backend.rules.result_builder import contains_any

    return contains_any(text, TRANSACTIONAL_BLOCK_KEYWORDS)


def has_hiring_intent(text: str) -> bool:
    from backend.rules.result_builder import contains_any, contains_word_any

    if contains_any(text, HIRING_INTENT_KEYWORDS):
        return True
    return contains_word_any(text, ["hiring", "jobs", "job", "role", "apply"])
