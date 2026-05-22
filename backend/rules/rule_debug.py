"""
Debug classification breakdown — rules pipeline visibility without Gmail fetch.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.paths import BACKEND_DEBUG_TRACES_DIR

TRACE_DIR = BACKEND_DEBUG_TRACES_DIR

from backend.services.classifier_service import EmailClassifier
from backend.config import load_config
from backend.rules.entity_special_rules import classify_entity_special
from backend.rules.fallback_rules import classify_fallback
from backend.rules.result_builder import prepare_email_context
from backend.rules.rule_engine import ENTITY_SHORT_CIRCUIT_CONFIDENCE, SAFETY_PIPELINE
from backend.rules.scored_rules import debug_scored_breakdown
from backend.rules.security_rules import classify_security
from backend.rules.spam_rules import classify_spam


def _save_debug_trace(payload: Dict[str, Any]) -> str:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    safe_subj = re.sub(r"[^\w.-]+", "_", (payload.get("subject") or "")[:40]).strip("_")
    path = TRACE_DIR / f"trace_{ts}_{safe_subj or 'email'}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def debug_classify(
    sender: str,
    subject: str,
    snippet: str = "",
    *,
    run_full_classifier: bool = True,
    save_trace: bool = False,
) -> Dict[str, Any]:
    """
    Return rule stages, per-category scores, vetoes, and optional full classifier path.
    """
    ctx = prepare_email_context(sender, subject, snippet)
    matched_rules: List[Dict[str, Any]] = []

    for stage_name, fn in SAFETY_PIPELINE:
        r = fn(ctx)
        if r:
            matched_rules.append(
                {"stage": stage_name, "category": r["category"], "confidence": r["confidence"], "reason": r.get("reason")}
            )
            breakdown = debug_scored_breakdown(ctx)
            return _assemble_debug_response(
                matched_rules=matched_rules,
                breakdown=breakdown,
                pipeline_result=r,
                sender=sender,
                subject=subject,
                snippet=snippet,
                run_full_classifier=run_full_classifier,
                save_trace=save_trace,
            )

    entity = classify_entity_special(ctx)
    if entity:
        matched_rules.append(
            {
                "stage": "entity_special",
                "category": entity["category"],
                "confidence": entity["confidence"],
                "reason": entity.get("reason"),
            }
        )
        if float(entity.get("confidence", 0)) >= ENTITY_SHORT_CIRCUIT_CONFIDENCE:
            breakdown = debug_scored_breakdown(ctx)
            return _assemble_debug_response(
                matched_rules=matched_rules,
                breakdown=breakdown,
                pipeline_result=entity,
                sender=sender,
                subject=subject,
                snippet=snippet,
                run_full_classifier=run_full_classifier,
                save_trace=save_trace,
            )

    breakdown = debug_scored_breakdown(ctx)
    scored = breakdown.get("winner")
    if scored:
        matched_rules.append(
            {
                "stage": "scored_orchestrator",
                "category": scored["category"],
                "confidence": scored["confidence"],
                "reason": scored.get("reason"),
            }
        )
        return _assemble_debug_response(
            matched_rules=matched_rules,
            breakdown=breakdown,
            pipeline_result=scored,
            sender=sender,
            subject=subject,
            snippet=snippet,
            run_full_classifier=run_full_classifier,
            save_trace=save_trace,
        )

    if entity:
        matched_rules.append(
            {
                "stage": "entity_special_low_conf",
                "category": entity["category"],
                "confidence": entity["confidence"],
                "reason": entity.get("reason"),
            }
        )
        return _assemble_debug_response(
            matched_rules=matched_rules,
            breakdown=breakdown,
            pipeline_result=entity,
            sender=sender,
            subject=subject,
            snippet=snippet,
            run_full_classifier=run_full_classifier,
            save_trace=save_trace,
        )

    fb = classify_fallback(ctx)
    matched_rules.append(
        {"stage": "fallback", "category": fb["category"], "confidence": fb["confidence"], "reason": fb.get("reason")}
    )
    return _assemble_debug_response(
        matched_rules=matched_rules,
        breakdown=breakdown,
        pipeline_result=fb,
        sender=sender,
        subject=subject,
        snippet=snippet,
        run_full_classifier=run_full_classifier,
        save_trace=save_trace,
    )


def _assemble_debug_response(
    *,
    matched_rules: List[Dict[str, Any]],
    breakdown: Dict[str, Any],
    pipeline_result: Dict[str, Any],
    sender: str,
    subject: str,
    snippet: str,
    run_full_classifier: bool,
    save_trace: bool = False,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "matched_rules": matched_rules,
        "positive_scores": breakdown.get("positive_scores", {}),
        "negative_scores": breakdown.get("negative_scores", {}),
        "category_scores": breakdown.get("category_scores", {}),
        "vetoes": breakdown.get("vetoes", []),
        "rules_only_category": pipeline_result.get("category"),
        "rules_only_confidence": pipeline_result.get("confidence"),
        "semantic_triggered": False,
        "groq_triggered": False,
        "final_category": pipeline_result.get("category"),
        "confidence": pipeline_result.get("confidence"),
        "source": pipeline_result.get("source", "rules"),
        "top_category": breakdown.get("top_category"),
        "second_category": breakdown.get("second_category"),
        "top_score": breakdown.get("top_score"),
        "second_score": breakdown.get("second_score"),
        "score_margin": breakdown.get("score_margin"),
        "low_margin": breakdown.get("low_margin"),
    }

    if run_full_classifier:
        clf = EmailClassifier()
        email = {"sender": sender, "subject": subject, "snippet": snippet, "body": ""}
        full = clf.classify_email(email)
        src = (full.get("source") or "").lower()
        out["semantic_triggered"] = src in ("semantic", "rules_verified")
        out["groq_triggered"] = src == "groq_escalation"
        out["final_category"] = full.get("category")
        out["confidence"] = full.get("confidence")
        out["source"] = full.get("source")
        out["reason"] = full.get("reason")
        out["full_classifier"] = full
    else:
        out["reason"] = pipeline_result.get("reason")

    if save_trace:
        trace_payload = {
            **out,
            "sender": sender,
            "subject": subject,
            "snippet": snippet,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        out["trace_file"] = _save_debug_trace(trace_payload)

    return out
