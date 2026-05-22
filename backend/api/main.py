import logging
import time

from contextlib import asynccontextmanager
from typing import List, Optional



from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, ConfigDict, Field



from backend.services.actions import GmailActions

from backend.services.classifier_service import EmailClassifier

from backend.api.api_errors import error_payload, register_exception_handlers
from backend.config import get_cors_origins, is_production, load_config, resolve_gmail_query
from backend.services.cycle_runner import execute_inbox_cycle
from backend.infrastructure.health.health_service import build_health_status
from backend.services.scheduler import scheduler_status, start_scheduler, stop_scheduler

from backend.infrastructure.gmail.gmail_client import GmailClient

from backend.services.inbox_processing import (
    build_processing_metrics,
    get_processing_limits,
    scan_inbox_for_actionable,
)
from backend.services.reporting import build_compact_cycle_report

from backend.category_metadata import get_category_metadata
from backend.storage.corrections_store import corrections_store, normalize_sender_key
from backend.services.dashboard_service import (
    get_daily_metrics_history,
    get_dashboard_overview,
    get_recent_activity,
    get_recent_failures,
)
from backend.evaluation.confusion_report import build_confusion_report
from backend.storage.metrics import metrics_store
from backend.services.cycle_manager import cycle_manager
from backend.services.operations import (
    record_classification_batch,
    record_correction_metric,
    record_cycle_run_metrics,
    record_daily_snapshot,
)
from backend.storage.processed_store import ProcessedEmailStore
from backend.services.review_queue import build_review_queue
from backend.rules.rule_debug import debug_classify
from backend.api.schemas import ReviewQueueItem
from backend.infrastructure.health.system_health import build_config_summary



_log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from backend.infrastructure.health.startup_check import run_startup_validation

    summary = run_startup_validation(strict=False)
    app.state.startup = summary
    start_scheduler(gmail, classifier)
    yield
    stop_scheduler()


# =========================================================

# APP

# =========================================================



_cfg = load_config()
_prod = is_production(_cfg)

app = FastAPI(
    title="Gmail Genie API",
    version="1.0.0",
    lifespan=_lifespan,
    docs_url=None if _prod else "/docs",
    redoc_url=None if _prod else "/redoc",
    openapi_url=None if _prod else "/openapi.json",
)

register_exception_handlers(app)





# =========================================================

# CORS

# =========================================================



_cors_origins = get_cors_origins(_cfg)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





# =========================================================

# SERVICES

# =========================================================



gmail = GmailClient()

classifier = EmailClassifier()





# =========================================================

# REQUEST MODELS

# =========================================================



class AnalyzedEmail(BaseModel):

    message_id: str = Field(..., description="Gmail message ID")

    category: str

    confidence: float

    sender: Optional[str] = None

    subject: Optional[str] = None

    snippet: Optional[str] = None

    source: Optional[str] = None

    reason: Optional[str] = None





class ApplyActionsRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "emails": [
                        {
                            "message_id": "0000000000000000",
                            "category": "Newsletters",
                            "confidence": 0.95,
                        }
                    ],
                    "dry_run": True,
                    "verbose": False,
                    "force_reprocess": False,
                }
            ]
        }
    )

    emails: List[AnalyzedEmail]
    dry_run: bool = Field(default=True, description="If true, plan actions without mutating Gmail.")
    verbose: bool = Field(default=False)
    force_reprocess: bool = Field(
        default=False,
        description="Bypass SQLite dedup only. Use for debugging/replay — not normal runs.",
    )





class AnalyzeAndApplyRequest(BaseModel):

    model_config = ConfigDict(

        json_schema_extra={

            "examples": [
                {
                    "max_results": 10,
                    "dry_run": True,
                    "force_reprocess": False,
                }
            ]

        }

    )



    max_results: int = Field(default=25, ge=1, le=100)

    dry_run: bool = True

    verbose: bool = False

    gmail_query: Optional[str] = Field(

        default=None,

        description=(

            "Optional Gmail search override. Omit (or leave null) to use "

            "config.yaml app.gmail_query."

        ),

        examples=["newer_than:7d"],

    )

    force_reprocess: bool = Field(
        default=False,
        description="Bypass SQLite dedup only. Use for debugging/replay — not normal runs.",
    )


class DailyCycleRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"max_results": 25, "dry_run": True, "force_reprocess": False}]
        }
    )

    max_results: int = Field(default=25, ge=1, le=100)
    dry_run: bool = Field(
        default=True,
        description="If true, plan actions only (recommended for automation dry checks).",
    )
    verbose: bool = False
    gmail_query: Optional[str] = None
    force_reprocess: bool = False
    compact_report: bool = Field(
        default=True,
        description="Return compact operational summary alongside full payload.",
    )


def _fetch_and_filter_inbox(
    *,
    cfg: dict,
    query: str,
    target_unprocessed: Optional[int] = None,
    force_reprocess: bool,
    on_page=None,
):
    """Paginated newest-first scan until target actionable emails or page limit."""
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





# =========================================================

# HEALTH CHECK

# =========================================================



@app.get("/")

def health_check():

    return {

        "status": "ok",

        "service": "gmail-genie",

    }


@app.get("/startup")
def startup_summary():
    """Last startup validation result (set on app lifespan)."""
    summary = getattr(app.state, "startup", None)
    if summary is None:
        from backend.infrastructure.health.startup_check import run_startup_validation

        summary = run_startup_validation(strict=False)
    return summary


class DebugClassifyRequest(BaseModel):
    sender: str = Field(..., examples=["DeepLearning.AI <newsletter@deeplearning.ai>"])
    subject: str = Field(..., examples=["The Batch @ DeepLearning.AI — Issue 42"])
    snippet: str = Field(default="", examples=["Weekly AI newsletter digest"])
    run_full_classifier: bool = Field(
        default=False,
        description="If true, also run full classifier (may invoke semantic/Groq).",
    )
    save_trace: bool = Field(
        default=False,
        description="If true, persist rule trace JSON under backend/debug_traces/ (ignored in production).",
    )


class CorrectClassificationRequest(BaseModel):
    message_id: Optional[str] = Field(
        default=None,
        description="Gmail message ID (optional; stored for audit only).",
    )
    sender: str = Field(..., examples=["DeepLearning.AI <newsletter@deeplearning.ai>"])
    corrected_category: str = Field(..., examples=["Newsletters"])
    previous_category: Optional[str] = Field(
        default=None,
        examples=["Finance"],
        description="Category before user correction (for confusion tracking).",
    )


@app.post("/debug-classify")
def debug_classify_endpoint(request: DebugClassifyRequest):
    """Rule score breakdown + optional full classification path."""
    if _prod:
        return JSONResponse(
            status_code=403,
            content=error_payload("Debug endpoints disabled in production"),
        )
    cfg = load_config()
    save_trace = request.save_trace and not is_production(cfg)
    return debug_classify(
        request.sender,
        request.subject,
        request.snippet,
        run_full_classifier=request.run_full_classifier,
        save_trace=save_trace,
    )


@app.get("/metrics-summary")
def metrics_summary():
    """Session classification counters (resets when API process restarts)."""
    from backend.storage.daily_metrics_store import daily_metrics_store

    from backend.infrastructure.gmail.gmail_transport import transport_metrics

    body = metrics_store.summary()
    body["success"] = True
    body["gmail_transport"] = transport_metrics.to_dict()
    body["cycle_status"] = cycle_manager.status()
    body["scheduler"] = scheduler_status()
    body["historical_totals"] = daily_metrics_store.get_historical_totals()
    last_run = daily_metrics_store.get_latest_cycle_run()
    body["last_cycle_run"] = last_run
    # When in-memory session counters are empty (e.g. after API restart), surface last run.
    if last_run and not body.get("total_classified"):
        classified = int(last_run.get("classified") or 0)
        semantic_used = int(last_run.get("semantic_used") or 0)
        groq_used = int(last_run.get("groq_used") or 0)
        rules_direct = max(0, classified - semantic_used - groq_used)
        denom = classified or 1
        body["total_classified"] = classified
        body["rules_direct_rate"] = round(rules_direct / denom, 4)
        body["rules_verified_rate"] = round(
            min(semantic_used, classified) / denom, 4
        )
        body["semantic_fallback_rate"] = float(last_run.get("semantic_rate") or 0)
        body["semantic_rate"] = body["semantic_fallback_rate"]
        body["from_last_cycle_run"] = True
    return body


@app.get("/scheduler-status")
def get_scheduler_status():
    return {"success": True, **scheduler_status()}


@app.get("/cycle-status")
def cycle_status():
    """Live inbox cycle state for operations UI polling."""
    from backend.storage.daily_metrics_store import daily_metrics_store

    from backend.infrastructure.gmail.gmail_transport import transport_metrics

    status = cycle_manager.status()
    status["latency"] = metrics_store.summary().get("latency", {})
    status["gmail_transport"] = transport_metrics.to_dict()
    status["historical_totals"] = daily_metrics_store.get_historical_totals()
    latest = daily_metrics_store.get_latest_cycle_run()
    if latest and not status.get("running"):
        status["last_cycle_run"] = latest
    return {"success": True, **status}


@app.post("/correct-classification")
def correct_classification(request: CorrectClassificationRequest):
    """
    Record a user correction. Does not modify Gmail or re-run classification.
    """
    cfg = load_config()
    allowed = set(cfg.get("categories", []))
    corrected = request.corrected_category.strip()
    if corrected not in allowed:
        return {
            "ok": False,
            "error": f"Unknown category: {corrected}",
            "allowed_categories": sorted(allowed),
        }
    correction_id = corrections_store.add_correction(
        message_id=request.message_id,
        sender=request.sender,
        corrected_category=corrected,
        previous_category=request.previous_category,
    )
    override = corrections_store.get_sender_override(request.sender)
    record_correction_metric()
    return {
        "ok": True,
        "correction_id": correction_id,
        "sender_key": normalize_sender_key(request.sender),
        "active_sender_override": override,
        "statistics": corrections_store.get_sender_statistics(),
        "review_note": "Correction recorded; sender override applies after 5 consistent fixes.",
    }


@app.get("/health")
def health():
    """Dependency and connectivity health (no secrets)."""
    return build_health_status(gmail)


@app.get("/onboarding-status")
def onboarding_status():
    """Setup checklist for local MVP onboarding."""
    from backend.services.onboarding_service import build_onboarding_status

    health = build_health_status(gmail)
    return build_onboarding_status(gmail, health)


@app.get("/pending-preview")
def pending_preview():
    """Restore last dry-run preview (survives dashboard navigation / refresh)."""
    last = cycle_manager.last_successful_cycle()
    if not last or not last.get("dry_run") or not last.get("awaiting_apply"):
        return {"success": True, "pending": None}
    return {"success": True, "pending": last}


@app.post("/pending-preview/dismiss")
def dismiss_pending_preview():
    """Clear awaiting-apply flag without running a new cycle."""
    cycle_manager.clear_awaiting_apply()
    return {"success": True}


@app.get("/undo-last-cycle")
def undo_last_cycle_info():
    """Whether the last applied cycle can be rolled back."""
    from backend.storage.cycle_undo_store import cycle_undo_store

    record = cycle_undo_store.get_last_cycle()
    return {"success": True, "undo": record}


@app.post("/undo-last-cycle")
def undo_last_cycle():
    """Remove Genie labels added in the last non-dry-run cycle only."""
    if cycle_manager.is_running():
        return JSONResponse(
            status_code=409,
            content=error_payload("Cannot undo while a cycle is running"),
        )
    from backend.services.undo_service import undo_last_cycle as do_undo

    try:
        return do_undo(gmail)
    except Exception as exc:
        _log.exception("undo-last-cycle failed")
        return JSONResponse(
            status_code=500,
            content=error_payload(str(exc)),
        )


@app.get("/config-summary")
def config_summary():
    """Safe configuration inspection for operations UI."""
    return build_config_summary()


@app.get("/dashboard/overview")
def dashboard_overview():
    """Operational summary for dashboard UI."""
    return get_dashboard_overview().model_dump()


@app.get("/dashboard/recent-activity")
def dashboard_recent_activity(limit: int = Query(default=50, ge=1, le=100)):
    return {"items": get_recent_activity(limit), "count": min(limit, 50)}


@app.get("/dashboard/recent-failures")
def dashboard_recent_failures(limit: int = Query(default=50, ge=1, le=100)):
    return get_recent_failures(limit)


@app.get("/dashboard/daily-metrics")
def dashboard_daily_metrics(limit: int = Query(default=30, ge=1, le=90)):
    return {"days": get_daily_metrics_history(limit)}


@app.get("/dashboard/category-metadata")
def dashboard_category_metadata():
    cfg = load_config()
    return get_category_metadata(cfg)


@app.get("/review-queue", response_model=List[ReviewQueueItem])
def review_queue(limit: int = Query(default=50, ge=1, le=100)):
    """Emails flagged for human review (low confidence, LLM, low score margin)."""
    cfg = load_config()
    threshold = float(cfg.get("app", {}).get("confidence_threshold", 0.70))
    return build_review_queue(limit, confidence_threshold=threshold)


@app.get("/dashboard/cycle-history")
def dashboard_cycle_history(limit: int = Query(default=30, ge=1, le=100)):
    from backend.storage.daily_metrics_store import daily_metrics_store

    return {
        "success": True,
        "runs": daily_metrics_store.list_cycle_runs(limit),
    }


@app.post("/run-daily-cycle")
def run_daily_cycle(request: DailyCycleRequest):
    """Production inbox cycle: fetch → filter → classify → apply."""
    if not cycle_manager.try_acquire():
        return JSONResponse(
            status_code=409,
            content=error_payload(
                "Inbox processing already running",
                extra={"cycle_status": cycle_manager.status()},
            ),
        )
    try:
        return execute_inbox_cycle(
            gmail,
            classifier,
            dry_run=request.dry_run,
            max_results=request.max_results,
            gmail_query=request.gmail_query,
            force_reprocess=request.force_reprocess,
            verbose=request.verbose,
            compact_report=request.compact_report,
            trigger="manual",
        )
    except TimeoutError as exc:
        cycle_manager.mark_failed(str(exc))
        return JSONResponse(
            status_code=503,
            content=error_payload(
                "Gmail API timed out. Check network or increase gmail.http_timeout_seconds.",
                details=str(exc),
                stage=cycle_manager.status().get("current_stage"),
                extra={"cycle_status": cycle_manager.status()},
            ),
        )
    except Exception as exc:
        cycle_manager.mark_failed(str(exc))
        _log.exception("run-daily-cycle failed")
        return JSONResponse(
            status_code=500,
            content=error_payload(
                str(exc),
                stage=cycle_manager.status().get("current_stage"),
                extra={"cycle_status": cycle_manager.status()},
            ),
        )
    finally:
        cycle_manager.release()


@app.get("/confusion-report")
def confusion_report():
    """Confusion pairs from last offline eval + stored user corrections."""
    report = build_confusion_report()
    return {
        "confusion": report,
        "pair_count": len(report),
        "sources": {
            "last_eval": "backend/evaluation/last_eval.json",
            "corrections_db": "backend/data/corrections.db",
        },
    }


# =========================================================

# ANALYZE EMAILS

# =========================================================



@app.get("/analyze")

def analyze_emails(

    max_results: int = 10,

    gmail_query: Optional[str] = None,

    force_reprocess: bool = Query(
        default=False,
        description="Bypass SQLite dedup only. Use for debugging/replay — not normal runs.",
    ),
):
    cfg = load_config()

    query = resolve_gmail_query(gmail_query, cfg)

    limits = get_processing_limits(cfg)
    target = min(
        max_results,
        limits["target_unprocessed_per_cycle"],
        cfg.get("app", {}).get("max_emails", 25),
    )

    scan, _store = _fetch_and_filter_inbox(
        cfg=cfg,
        query=query,
        target_unprocessed=target,
        force_reprocess=force_reprocess,
    )
    filtered = scan.filter_result

    metrics_store.record_skips(
        label_skipped=len(filtered.label_skipped),
        dedup_skipped=len(filtered.dedup_skipped),
    )

    classifications = classifier.batch_classify_emails(filtered.to_process)
    record_classification_batch(filtered.to_process, classifications)

    results = []

    for email, classification in zip(filtered.to_process, classifications):

        results.append(

            {

                "message_id": email.get("id"),

                "sender": email.get("sender"),

                "subject": email.get("subject"),

                "snippet": email.get("snippet"),

                "category": classification.get("category"),

                "confidence": classification.get("confidence"),

                "source": classification.get("source"),

                "reason": classification.get("reason"),

            }

        )



    metrics = build_processing_metrics(
        scan=scan,
        classifications=classifications,
        actions_applied=0,
    )

    return {
        "gmail_query": query,
        "emails": results,
        "label_skipped_emails": filtered.label_skipped,
        "dedup_skipped_emails": filtered.dedup_skipped,
        "status_messages": scan.status_messages,
        **metrics,
    }





# =========================================================

# APPLY GMAIL ACTIONS

# =========================================================



@app.post("/apply-actions")

def apply_actions(request: ApplyActionsRequest):

    cfg = load_config()

    processing_cfg = cfg.get("processing", {}) or {}

    deduplicate = bool(processing_cfg.get("deduplicate", True))

    store = ProcessedEmailStore()



    incoming = [email.model_dump() for email in request.emails]

    if deduplicate and not request.force_reprocess:

        filtered = []

        skipped = []

        for item in incoming:

            mid = item.get("message_id")

            if mid and store.has_been_processed(mid):

                _log.info("[DEDUP SKIP] message_id=%s", mid)

                skipped.append({**item, "skipped_reason": "already_processed"})

            else:

                filtered.append(item)

        payload = filtered

    else:

        skipped = []

        payload = incoming



    actions = GmailActions(

        gmail_client=gmail,

        config=cfg,

        dry_run=request.dry_run,

        verbose=request.verbose,

    )



    result = actions.process_batch_results(payload)



    if deduplicate and not request.dry_run:

        for item in result.get("emails", []):

            mid = item.get("message_id")

            if not mid:

                continue

            store.mark_processed(

                message_id=mid,

                category=item.get("category", "General"),

                confidence=float(item.get("confidence", 0.0)),

                action_applied=bool(item.get("applied", False)),

            )

        _log.info("[ACTIONS APPLIED] count=%s", result.get("applied", 0))



    if skipped:

        result = {

            **result,

            "dedup_skipped": len(skipped),

            "dedup_skipped_emails": skipped,

        }

    return result





@app.post("/analyze-and-apply")

def analyze_and_apply(request: AnalyzeAndApplyRequest):

    cfg = load_config()

    processing_cfg = cfg.get("processing", {}) or {}

    deduplicate = bool(processing_cfg.get("deduplicate", True))



    query = resolve_gmail_query(request.gmail_query, cfg)

    limits = get_processing_limits(cfg)
    target = min(
        request.max_results,
        limits["target_unprocessed_per_cycle"],
        cfg.get("app", {}).get("max_emails", 25),
    )

    scan, store = _fetch_and_filter_inbox(
        cfg=cfg,
        query=query,
        target_unprocessed=target,
        force_reprocess=request.force_reprocess,
    )
    filtered = scan.filter_result

    metrics_store.record_skips(
        label_skipped=len(filtered.label_skipped),
        dedup_skipped=len(filtered.dedup_skipped),
    )

    classifications = classifier.batch_classify_emails(filtered.to_process)

    analyzed_payload = []

    combined_emails = []

    for email, classification in zip(filtered.to_process, classifications):

        item = {

            "message_id": str(email.get("id")),

            "sender": email.get("sender"),

            "subject": email.get("subject"),

            "snippet": email.get("snippet"),

            "category": classification.get("category"),

            "confidence": classification.get("confidence"),

            "source": classification.get("source"),

            "reason": classification.get("reason"),

        }

        combined_emails.append(item)

        analyzed_payload.append(

            {

                "message_id": item["message_id"],

                "category": item["category"],

                "confidence": item["confidence"],

            }

        )



    actions = GmailActions(

        gmail_client=gmail,

        config=cfg,

        dry_run=request.dry_run,

        verbose=request.verbose,

    )

    apply_result = actions.process_batch_results(analyzed_payload)
    action_outcomes = {
        str(e.get("message_id")): e for e in apply_result.get("emails", [])
    }
    record_classification_batch(
        filtered.to_process,
        classifications,
        action_outcomes=action_outcomes,
    )

    if deduplicate and not request.dry_run:

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

        _log.info("[ACTIONS APPLIED] count=%s", apply_result.get("applied", 0))

    applied = int(apply_result.get("applied", 0))
    metrics = build_processing_metrics(
        scan=scan,
        classifications=classifications,
        actions_applied=applied,
    )
    record_daily_snapshot(
        processed=metrics["classified"],
        label_skipped=metrics["label_skipped"],
        semantic_used=metrics["semantic_used"],
        groq_used=metrics["groq_used"],
        top_categories=metrics_store.summary().get("category_distribution"),
    )

    outcome_by_id = {e.get("message_id"): e for e in apply_result.get("emails", [])}

    output_emails = []

    for item in combined_emails:

        outcome = outcome_by_id.get(item["message_id"], {})

        output_emails.append({**item, **outcome})

    response = {
        "gmail_query": query,
        "emails": output_emails,
        "label_skipped_emails": filtered.label_skipped,
        "dedup_skipped_emails": filtered.dedup_skipped,
        "status_messages": scan.status_messages,
        "apply_summary": {k: v for k, v in apply_result.items() if k != "emails"},
        **metrics,
    }
    if request.dry_run:
        response["report"] = build_compact_cycle_report(
            fetched=metrics["fetched_total"],
            classified=metrics["classified"],
            label_skipped=metrics["label_skipped"],
            dedup_skipped=metrics["dedup_skipped"],
            semantic_used=metrics["semantic_used"],
            groq_used=metrics["groq_used"],
            actions_applied=applied,
            classifications=classifications,
            dry_run=True,
            pages_scanned=metrics["pages_scanned"],
            fetched_total=metrics["fetched_total"],
            actionable_found=metrics["actionable_found"],
        )
    return response


