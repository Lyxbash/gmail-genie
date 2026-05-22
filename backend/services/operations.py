"""
Operational event recording (dashboard / review) — no classifier changes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.storage.activity_store import activity_store
from backend.config import load_config
from backend.storage.daily_metrics_store import daily_metrics_store
from backend.infrastructure.llm.rule_trust import is_strong_rule_match
from backend.rules.score_margin import compute_score_margin_for_email, review_reason_from_signals


def record_classification_batch(
    emails: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
    *,
    action_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """
    Log classified emails for dashboard and review queue.

    ``action_outcomes`` maps message_id -> apply result dict with ``applied`` key.
    """
    cfg = load_config()
    threshold = float(cfg.get("app", {}).get("confidence_threshold", 0.70))
    action_outcomes = action_outcomes or {}

    for email, classification in zip(emails, classifications):
        mid = str(email.get("id") or email.get("message_id") or "")
        sender = email.get("sender") or ""
        subject = email.get("subject") or ""
        snippet = email.get("snippet") or ""
        category = classification.get("category", "General")
        confidence = float(classification.get("confidence", 0))
        source = classification.get("source") or "rules"

        margin_info = compute_score_margin_for_email(sender, subject, snippet)
        rules_trusted = bool(classification.get("rules_trusted")) or is_strong_rule_match(
            {"category": category, "confidence": confidence, "reason": classification.get("reason", "")}
        )
        review_reason = review_reason_from_signals(
            confidence=confidence,
            source=source,
            score_margin=margin_info.get("score_margin"),
            low_margin=bool(margin_info.get("low_margin")),
            confidence_threshold=threshold,
            rules_trusted=rules_trusted,
        )
        if review_reason:
            from backend.storage.metrics import metrics_store

            metrics_store.record_review_reason(review_reason)

        outcome = action_outcomes.get(mid, {})
        action_applied = bool(outcome.get("applied", False))

        activity_store.record(
            message_id=mid or None,
            sender=sender,
            subject=subject,
            snippet=snippet,
            category=category,
            confidence=confidence,
            source=source,
            action_applied=action_applied,
            score_margin=margin_info.get("score_margin"),
            top_score=margin_info.get("top_score"),
            second_category=margin_info.get("second_category"),
            review_reason=review_reason,
        )


def record_daily_snapshot(
    *,
    processed: int,
    label_skipped: int,
    semantic_used: int,
    groq_used: int,
    top_categories: Optional[Dict[str, int]] = None,
) -> None:
    daily_metrics_store.record_cycle(
        processed=processed,
        label_skipped=label_skipped,
        semantic_used=semantic_used,
        groq_used=groq_used,
        corrections=0,
        top_categories=top_categories,
    )


def record_cycle_run_metrics(
    *,
    started_at: Optional[str],
    dry_run: bool,
    metrics: Dict[str, Any],
    latency: Dict[str, float],
    status: str = "ok",
    semantic_rate: float = 0.0,
    top_categories: Optional[Dict[str, int]] = None,
) -> None:
    """Persist per-cycle latency and counts to daily_metrics.db."""
    from datetime import datetime, timezone

    completed_at = datetime.now(timezone.utc).isoformat()
    daily_metrics_store.record_cycle_run(
        started_at=started_at,
        completed_at=completed_at,
        dry_run=dry_run,
        pages_scanned=int(metrics.get("pages_scanned", 0)),
        fetched_total=int(metrics.get("fetched_total", 0)),
        label_skipped=int(metrics.get("label_skipped", 0)),
        dedup_skipped=int(metrics.get("dedup_skipped", 0)),
        classified=int(metrics.get("classified", 0)),
        actions_applied=int(metrics.get("actions_applied", 0)),
        semantic_used=int(metrics.get("semantic_used", 0)),
        groq_used=int(metrics.get("groq_used", 0)),
        gmail_fetch_ms=float(latency.get("gmail_fetch_ms", 0)),
        filtering_ms=float(latency.get("filtering_ms", 0)),
        classify_ms=float(latency.get("classify_ms", 0)),
        actions_ms=float(latency.get("actions_ms", 0)),
        total_cycle_ms=float(latency.get("total_cycle_ms", 0)),
        status=status,
        semantic_rate=semantic_rate,
        top_categories=top_categories,
    )


def record_correction_metric() -> None:
    daily_metrics_store.record_cycle(corrections=1)
