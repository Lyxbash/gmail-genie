"""
Shared inbox cycle execution (manual API + scheduler).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backend.services.actions import GmailActions
from backend.config import load_config, resolve_gmail_query
from backend.services.cycle_manager import STAGE_APPLYING, STAGE_CLASSIFYING, STAGE_SKIPPING, cycle_manager
from backend.services.inbox_processing import (
    build_processing_metrics,
    get_processing_limits,
    scan_inbox_for_actionable,
)
from backend.storage.cycle_undo_store import cycle_undo_store
from backend.infrastructure.gmail.gmail_transport import transport_metrics
from backend.infrastructure.logging.logging_setup import get_cycle_logger
from backend.storage.metrics import metrics_store
from backend.services.operations import (
    record_classification_batch,
    record_cycle_run_metrics,
    record_daily_snapshot,
)
from backend.storage.processed_store import ProcessedEmailStore
from backend.services.reporting import build_compact_cycle_report

_log = logging.getLogger(__name__)
_cycle_log = get_cycle_logger()


def _build_classified_emails(
    emails: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
    apply_emails: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Full per-message preview rows for UI (dry-run review before apply)."""
    outcome_by_id = {
        str(e.get("message_id")): e
        for e in apply_emails
        if e.get("message_id")
    }
    rows: List[Dict[str, Any]] = []
    for email, classification in zip(emails, classifications):
        mid = str(email.get("id") or "")
        outcome = outcome_by_id.get(mid, {})
        rows.append(
            {
                "message_id": mid,
                "sender": email.get("sender") or "",
                "subject": email.get("subject") or "",
                "category": classification.get("category", "General"),
                "confidence": float(classification.get("confidence", 0.0)),
                "source": classification.get("source", "rules"),
                "would_apply_label": bool(outcome.get("applied")),
                "planned_labels": outcome.get("labels")
                or outcome.get("apply_label_names")
                or [],
                "skipped_reason": outcome.get("skipped_reason"),
            }
        )
    return rows


def _fetch_and_filter_inbox(
    gmail,
    *,
    cfg: dict,
    query: str,
    target_unprocessed: Optional[int],
    force_reprocess: bool,
    on_page=None,
):
    store = ProcessedEmailStore()
    limits = get_processing_limits(cfg)
    target = (
        target_unprocessed
        if target_unprocessed is not None
        else limits["target_unprocessed_per_cycle"]
    )
    scan = scan_inbox_for_actionable(
        gmail,
        config=cfg,
        query=query,
        store=store,
        force_reprocess=force_reprocess,
        target_unprocessed=target,
        on_page=on_page,
    )
    return scan, store


def execute_inbox_cycle(
    gmail,
    classifier,
    *,
    dry_run: bool = True,
    max_results: int = 25,
    gmail_query: Optional[str] = None,
    force_reprocess: bool = False,
    verbose: bool = False,
    compact_report: bool = True,
    trigger: str = "manual",
) -> Dict[str, Any]:
    """
    Run full inbox pipeline. Caller must hold ``cycle_manager`` lock.
    """
    cfg = load_config()
    processing_cfg = cfg.get("processing", {}) or {}
    deduplicate = bool(processing_cfg.get("deduplicate", True))

    query = resolve_gmail_query(gmail_query, cfg)
    limits = get_processing_limits(cfg)
    target = min(
        max_results,
        limits["target_unprocessed_per_cycle"],
        cfg.get("app", {}).get("max_emails", 25),
    )

    started_at = cycle_manager.status().get("started_at")

    _cycle_log.info(
        "Cycle start trigger=%s dry_run=%s target=%d query=%s",
        trigger,
        dry_run,
        target,
        query,
    )

    metrics_store.start_cycle()
    transport_metrics.reset_cycle()
    t_cycle = time.perf_counter()
    cycle_manager.set_stage("scanning")

    def _on_page(**kwargs) -> None:
        if kwargs.get("label_skipped") or kwargs.get("dedup_skipped"):
            cycle_manager.set_stage(STAGE_SKIPPING)
        cycle_manager.update_progress(**kwargs)

    scan, store = _fetch_and_filter_inbox(
        gmail,
        cfg=cfg,
        query=query,
        target_unprocessed=target,
        force_reprocess=force_reprocess,
        on_page=_on_page,
    )
    filtered = scan.filter_result
    status_messages: List[str] = list(scan.status_messages)
    metrics_store.record_scan_timings(scan)
    cycle_manager.update_progress(
        pages_scanned=scan.pages_scanned,
        fetched_total=scan.fetched_total,
        label_skipped=len(filtered.label_skipped),
        dedup_skipped=len(filtered.dedup_skipped),
        partial_fetch_failures=scan.partial_fetch_failures,
    )
    metrics_store.record_skips(
        label_skipped=len(filtered.label_skipped),
        dedup_skipped=len(filtered.dedup_skipped),
    )

    cycle_manager.set_stage(STAGE_CLASSIFYING)
    t_classify = time.perf_counter()
    classifications = classifier.batch_classify_emails(filtered.to_process)
    metrics_store.record_phase_ms("classify", (time.perf_counter() - t_classify) * 1000)
    cycle_manager.update_progress(classified=len(filtered.to_process))

    analyzed_payload = []
    for email, classification in zip(filtered.to_process, classifications):
        analyzed_payload.append(
            {
                "message_id": str(email.get("id")),
                "category": classification.get("category"),
                "confidence": classification.get("confidence"),
            }
        )

    actions = GmailActions(
        gmail_client=gmail,
        config=cfg,
        dry_run=dry_run,
        verbose=verbose,
    )
    cycle_manager.set_stage(STAGE_APPLYING)
    status_messages.append("Applying actions...")
    t_actions = time.perf_counter()
    apply_result = actions.process_batch_results(analyzed_payload)
    metrics_store.record_phase_ms("actions", (time.perf_counter() - t_actions) * 1000)
    applied = int(apply_result.get("applied", 0))
    action_outcomes = {str(e.get("message_id")): e for e in apply_result.get("emails", [])}

    undo_cycle_id: Optional[str] = None
    if not dry_run and applied > 0:
        undo_entries = []
        for item in apply_result.get("emails", []):
            if not item.get("applied"):
                continue
            labels = item.get("labels") or item.get("apply_label_names") or []
            if not labels:
                continue
            undo_entries.append(
                {
                    "message_id": str(item.get("message_id")),
                    "labels_added": list(labels),
                    "category": item.get("category"),
                }
            )
        if undo_entries:
            undo_cycle_id = cycle_undo_store.save_cycle(
                started_at=started_at,
                gmail_query=query,
                entries=undo_entries,
            )
    t_db = time.perf_counter()
    record_classification_batch(
        filtered.to_process,
        classifications,
        action_outcomes=action_outcomes,
    )

    if deduplicate and not dry_run:
        for item in apply_result.get("emails", []):
            mid = item.get("message_id")
            if not mid:
                continue
            store.mark_processed(
                message_id=mid,
                category=item.get("category", "General"),
                confidence=float(item.get("confidence", 0.0)),
                action_applied=bool(item.get("applied", False)),
            )
    metrics_store.record_phase_ms("db_write", (time.perf_counter() - t_db) * 1000)

    metrics = build_processing_metrics(
        scan=scan,
        classifications=classifications,
        actions_applied=applied,
    )
    status_messages.append("Cycle complete.")
    metrics_store.end_cycle()
    cycle_duration_ms = round((time.perf_counter() - t_cycle) * 1000, 1)
    session_metrics = metrics_store.summary()
    latency = session_metrics.get("latency") or {}
    latency["total_cycle_ms"] = cycle_duration_ms

    n_classified = metrics.get("classified") or 0
    semantic_rate = round(metrics.get("semantic_used", 0) / max(n_classified, 1), 4)

    record_daily_snapshot(
        processed=metrics["classified"],
        label_skipped=metrics["label_skipped"],
        semantic_used=metrics["semantic_used"],
        groq_used=metrics["groq_used"],
        top_categories=session_metrics.get("category_distribution"),
    )
    record_cycle_run_metrics(
        started_at=started_at,
        dry_run=dry_run,
        metrics=metrics,
        latency=latency,
        semantic_rate=semantic_rate,
        top_categories=session_metrics.get("category_distribution"),
    )

    classified_emails = _build_classified_emails(
        filtered.to_process,
        classifications,
        apply_result.get("emails", []),
    )
    pending_apply = {
        "gmail_query": query,
        "max_results": target,
        "force_reprocess": force_reprocess,
    }

    cycle_summary = {
        **metrics,
        "dry_run": dry_run,
        "cycle_duration_ms": cycle_duration_ms,
        "latency": latency,
        "actions_applied": applied,
        "semantic_rate": semantic_rate,
        "trigger": trigger,
        "undo_cycle_id": undo_cycle_id,
        "gmail_query": query,
        "classified_emails": classified_emails,
        "pending_apply": pending_apply,
        "awaiting_apply": bool(dry_run),
    }
    if dry_run:
        cycle_summary["preview"] = {
            "would_apply_labels": apply_result.get("would_apply_labels") or [],
            "would_mark_read": apply_result.get("would_mark_read") or [],
            "estimated_actions": applied,
            "classified_emails": classified_emails,
        }
    cycle_manager.mark_complete(cycle_summary)

    _cycle_log.info(
        "Cycle done trigger=%s classified=%d actions=%d duration_ms=%s",
        trigger,
        metrics.get("classified"),
        applied,
        cycle_duration_ms,
    )

    partial_failures = int(metrics.get("partial_fetch_failures") or 0)
    live_status = cycle_manager.status()
    body: Dict[str, Any] = {
        "success": True,
        "status": "partial_success" if partial_failures > 0 else "ok",
        "cycle_state": live_status.get("cycle_state"),
        "gmail_query": query,
        "dry_run": dry_run,
        "status_messages": status_messages,
        "cycle_duration_ms": cycle_duration_ms,
        "apply_summary": {k: v for k, v in apply_result.items() if k != "emails"},
        "session_metrics": session_metrics,
        "gmail_transport": transport_metrics.to_dict(),
        "cycle_status": live_status,
        **metrics,
        "latency": latency,
        "classification_paths": session_metrics.get("classification_paths"),
        "review_reason_breakdown": session_metrics.get("review_reason_breakdown"),
    }
    report = None
    if compact_report:
        report = build_compact_cycle_report(
            fetched=metrics["fetched_total"],
            classified=metrics["classified"],
            label_skipped=metrics["label_skipped"],
            dedup_skipped=metrics["dedup_skipped"],
            semantic_used=metrics["semantic_used"],
            groq_used=metrics["groq_used"],
            actions_applied=applied,
            classifications=classifications,
            dry_run=dry_run,
            pages_scanned=metrics["pages_scanned"],
            fetched_total=metrics["fetched_total"],
            actionable_found=metrics["actionable_found"],
        )
        body["report"] = report
    body["classified_emails"] = classified_emails
    body["pending_apply"] = pending_apply
    body["awaiting_apply"] = bool(dry_run)
    if dry_run:
        body["preview"] = {
            "classified_emails": classified_emails,
            "would_apply_labels": apply_result.get("would_apply_labels") or [],
            "would_mark_read": apply_result.get("would_mark_read") or [],
            "estimated_actions": applied,
            "category_counts": (report or {}).get("top_categories") or {},
        }
    last_undo = cycle_undo_store.get_last_cycle()
    body["undo_available"] = bool(last_undo and last_undo.get("can_undo"))
    saved = cycle_manager.last_successful_cycle()
    if saved:
        body["completed_at"] = saved.get("completed_at")
    return body
