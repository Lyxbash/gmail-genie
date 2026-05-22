"""

Dashboard aggregation for operations visibility.

"""



from __future__ import annotations



import json

from collections import Counter

from pathlib import Path

from typing import Any, Dict, List, Optional



from backend.storage.activity_store import activity_store

from backend.storage.corrections_store import corrections_store

from backend.services.cycle_manager import cycle_manager

from backend.storage.daily_metrics_store import daily_metrics_store

from backend.storage.metrics import metrics_store

from backend.storage.processed_store import ProcessedEmailStore

from backend.api.schemas import (

    ActivityItem,

    CurrentCycleSnapshot,

    DashboardOverview,

    HistoricalTotals,

)



from backend.paths import BACKEND_EVAL_DIR

EVAL_LAST_PATH = BACKEND_EVAL_DIR / "last_eval.json"
FAILURES_PATH = BACKEND_EVAL_DIR / "failures.json"





def _load_accuracy_estimate() -> Optional[float]:

    if not EVAL_LAST_PATH.is_file():

        return None

    try:

        data = json.loads(EVAL_LAST_PATH.read_text(encoding="utf-8"))

        acc = data.get("accuracy")

        if acc is not None:

            return round(float(acc), 4)

    except (json.JSONDecodeError, OSError, TypeError, ValueError):

        pass

    return None





def _build_current_cycle_snapshot() -> CurrentCycleSnapshot:

    live = cycle_manager.status()

    if live.get("running"):

        return CurrentCycleSnapshot(

            pages_scanned=int(live.get("pages_scanned") or 0),

            fetched_total=int(live.get("fetched_total") or 0),

            label_skipped=int(live.get("label_skipped") or 0),

            dedup_skipped=int(live.get("dedup_skipped") or 0),

            classified=int(live.get("classified") or 0),

            partial_fetch_failures=int(live.get("partial_fetch_failures") or 0),

            running=True,

            current_stage=str(live.get("current_stage") or "scanning"),

            cycle_state=str(live.get("cycle_state") or "running"),

            started_at=live.get("started_at"),

            elapsed_seconds=live.get("elapsed_seconds"),

            heartbeat_stale=bool(live.get("heartbeat_stale")),

        )



    last = cycle_manager.last_successful_cycle()

    if last:

        latency = last.get("latency") or {}

        return CurrentCycleSnapshot(

            pages_scanned=int(last.get("pages_scanned") or 0),

            fetched_total=int(last.get("fetched_total") or 0),

            label_skipped=int(last.get("label_skipped") or 0),

            dedup_skipped=int(last.get("dedup_skipped") or 0),

            classified=int(last.get("classified") or 0),

            actions_applied=int(last.get("actions_applied") or 0),

            cycle_duration_ms=float(

                last.get("cycle_duration_ms")

                or latency.get("total_cycle_ms")

                or 0

            ),

            dry_run=bool(last.get("dry_run")),

            completed_at=last.get("completed_at"),

            started_at=last.get("started_at"),

            latency=latency,

            running=False,

            current_stage="idle",

            cycle_state=str(last.get("cycle_state") or last.get("status") or "completed"),

            partial_fetch_failures=int(last.get("partial_fetch_failures") or 0),

        )



    db_last = daily_metrics_store.get_latest_cycle_run()

    if db_last:

        latency = db_last.get("latency") or {}

        return CurrentCycleSnapshot(

            pages_scanned=int(db_last.get("pages_scanned") or 0),

            fetched_total=int(db_last.get("fetched_total") or 0),

            label_skipped=int(db_last.get("label_skipped") or 0),

            dedup_skipped=int(db_last.get("dedup_skipped") or 0),

            classified=int(db_last.get("classified") or 0),

            actions_applied=int(db_last.get("actions_applied") or 0),

            cycle_duration_ms=float(latency.get("total_cycle_ms") or 0),

            dry_run=bool(db_last.get("dry_run")),

            completed_at=db_last.get("completed_at"),

            started_at=db_last.get("started_at"),

            latency=latency,

            running=False,

            current_stage="idle",

        )



    return CurrentCycleSnapshot()





def get_dashboard_overview() -> DashboardOverview:

    session = metrics_store.summary()

    processed_store = ProcessedEmailStore()



    try:

        cur = processed_store.conn.cursor()

        cur.execute("SELECT COUNT(*) FROM processed_emails")

        total_processed_db = int(cur.fetchone()[0])

    except Exception:

        total_processed_db = 0



    activity_total = activity_store.count_total()

    historical_db = daily_metrics_store.get_historical_totals()

    total_processed = max(

        total_processed_db,

        activity_total,

        historical_db.get("total_processed", 0),

        session.get("total_classified", 0),

    )



    historical = HistoricalTotals(

        total_processed=total_processed,

        total_label_skipped=int(historical_db.get("total_label_skipped", 0)),

        total_semantic_calls=int(historical_db.get("total_semantic_calls", 0)),

        total_groq_calls=int(historical_db.get("total_groq_calls", 0)),

        total_corrections=int(historical_db.get("total_corrections", 0)),

    )



    current_cycle = _build_current_cycle_snapshot()

    last_success = cycle_manager.last_successful_cycle()



    top_from_activity = activity_store.category_totals()

    top_from_session = session.get("category_distribution") or {}

    merged: Counter[str] = Counter()

    merged.update(top_from_activity)

    merged.update(top_from_session)

    top_categories = dict(merged.most_common(15))



    recent_raw = activity_store.list_recent(20)

    recent_activity = [

        ActivityItem(

            message_id=r.get("message_id"),

            sender=r.get("sender"),

            subject=r.get("subject"),

            category=r.get("category", "General"),

            confidence=r.get("confidence", 0),

            source=r.get("source", "rules"),

            action_applied=r.get("action_applied", False),

            score_margin=r.get("score_margin"),

            created_at=r.get("created_at", ""),

        )

        for r in recent_raw

    ]



    return DashboardOverview(

        historical=historical,

        current_cycle=current_cycle,

        last_successful_cycle=last_success,

        cycle_running=cycle_manager.is_running(),

        top_categories=top_categories,

        recent_activity=recent_activity,

        accuracy_estimate=_load_accuracy_estimate(),

        session_metrics=session,

        total_processed=historical.total_processed,

        label_skipped=historical.total_label_skipped,

        semantic_used=historical.total_semantic_calls,

        groq_used=historical.total_groq_calls,

    )





def get_recent_activity(limit: int = 50) -> List[Dict[str, Any]]:

    return activity_store.list_recent(limit)





def get_recent_failures(limit: int = 50) -> Dict[str, Any]:

    """Operational review queue inputs: eval failures, corrections, low confidence, LLM paths."""

    eval_failures: List[Dict[str, Any]] = []

    if FAILURES_PATH.is_file():

        try:

            eval_failures = json.loads(FAILURES_PATH.read_text(encoding="utf-8"))

            if not isinstance(eval_failures, list):

                eval_failures = []

        except (json.JSONDecodeError, OSError):

            eval_failures = []



    corrections = _list_recent_corrections(limit)

    low_confidence = activity_store.list_low_confidence(0.70, limit)

    llm_triggered = [

        r

        for r in activity_store.list_recent(limit * 2)

        if (r.get("source") or "").lower()

        in ("semantic", "groq_escalation", "rules_verified")

    ][:limit]



    return {

        "evaluation_failures": eval_failures[:limit],

        "corrected_emails": corrections[:limit],

        "low_confidence": low_confidence[:limit],

        "semantic_or_groq": llm_triggered[:limit],

        "counts": {

            "evaluation_failures": len(eval_failures),

            "corrected_emails": len(corrections),

            "low_confidence": len(low_confidence),

            "semantic_or_groq": len(llm_triggered),

        },

    }





def _list_recent_corrections(limit: int) -> List[Dict[str, Any]]:

    cur = corrections_store.conn.cursor()

    cur.execute(

        """

        SELECT id, message_id, sender, corrected_category, previous_category, created_at

        FROM user_corrections

        ORDER BY id DESC

        LIMIT ?

        """,

        (limit,),

    )

    return [

        {

            "id": row[0],

            "message_id": row[1],

            "sender": row[2],

            "corrected_category": row[3],

            "previous_category": row[4],

            "created_at": row[5],

        }

        for row in cur.fetchall()

    ]





def get_daily_metrics_history(limit: int = 30) -> List[Dict[str, Any]]:

    return daily_metrics_store.list_days(limit)


