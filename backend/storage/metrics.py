"""
In-process classification metrics (session counters, reset on process restart).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Dict, Optional  # Any for scan timing duck-type

from backend.infrastructure.llm.rule_trust import normalize_classification_path


class ClassificationMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.total_classified = 0
            self.rules_used = 0
            self.semantic_used = 0
            self.groq_used = 0
            self.label_skipped = 0
            self.dedup_skipped = 0
            self.confidence_sum = 0.0
            self.category_counts: Dict[str, int] = defaultdict(int)
            self.source_counts: Dict[str, int] = defaultdict(int)
            self.path_counts: Dict[str, int] = defaultdict(int)
            self.review_reason_counts: Dict[str, int] = defaultdict(int)
            self._cycle_start: Optional[float] = None
            self.cycle_duration_ms: float = 0.0
            self.gmail_list_ms: float = 0.0
            self.gmail_fetch_messages_ms: float = 0.0
            self.gmail_fetch_labels_ms: float = 0.0
            self.gmail_fetch_ms: float = 0.0
            self.filtering_ms: float = 0.0
            self.classify_ms: float = 0.0
            self.classify_rules_ms: float = 0.0
            self.classify_semantic_ms: float = 0.0
            self.actions_ms: float = 0.0
            self.actions_apply_ms: float = 0.0
            self.db_write_ms: float = 0.0
            self.total_cycle_ms: float = 0.0
            self._rules_latency_sum_ms: float = 0.0
            self._semantic_latency_sum_ms: float = 0.0
            self._rules_latency_n: int = 0
            self._semantic_latency_n: int = 0

    def _reset_classification_counters(self) -> None:
        """Clear per-cycle classification counters (called when a new cycle starts)."""
        self.total_classified = 0
        self.rules_used = 0
        self.semantic_used = 0
        self.groq_used = 0
        self.confidence_sum = 0.0
        self.category_counts = defaultdict(int)
        self.source_counts = defaultdict(int)
        self.path_counts = defaultdict(int)
        self.review_reason_counts = defaultdict(int)
        self._rules_latency_sum_ms = 0.0
        self._semantic_latency_sum_ms = 0.0
        self._rules_latency_n = 0
        self._semantic_latency_n = 0

    def start_cycle(self) -> None:
        with self._lock:
            self._cycle_start = time.perf_counter()
            self._reset_classification_counters()

    def end_cycle(self) -> None:
        with self._lock:
            if self._cycle_start is not None:
                self.cycle_duration_ms = (time.perf_counter() - self._cycle_start) * 1000
                self.total_cycle_ms = self.cycle_duration_ms
                self._cycle_start = None

    def record_scan_timings(self, scan: Any) -> None:
        with self._lock:
            self.gmail_list_ms = float(getattr(scan, "gmail_list_ms", 0) or 0)
            self.gmail_fetch_messages_ms = float(
                getattr(scan, "gmail_fetch_messages_ms", 0) or 0
            )
            self.gmail_fetch_labels_ms = float(
                getattr(scan, "gmail_fetch_labels_ms", 0) or 0
            )
            self.gmail_fetch_ms = float(getattr(scan, "gmail_api_ms", 0) or 0)
            self.filtering_ms = float(getattr(scan, "filtering_ms", 0) or 0)

    def record_phase_ms(self, phase: str, duration_ms: float) -> None:
        with self._lock:
            if phase == "gmail_fetch":
                self.gmail_fetch_ms += duration_ms
            elif phase == "filtering":
                self.filtering_ms += duration_ms
            elif phase == "classify":
                self.classify_ms += duration_ms
            elif phase == "actions":
                self.actions_ms += duration_ms
                self.actions_apply_ms += duration_ms
            elif phase == "db_write":
                self.db_write_ms += duration_ms

    def record_rules_latency(self, duration_ms: float) -> None:
        with self._lock:
            self._rules_latency_sum_ms += duration_ms
            self._rules_latency_n += 1
            self.classify_rules_ms += duration_ms

    def record_semantic_latency(self, duration_ms: float) -> None:
        with self._lock:
            self._semantic_latency_sum_ms += duration_ms
            self._semantic_latency_n += 1
            self.classify_semantic_ms += duration_ms

    def record_classification(self, result: Dict[str, Any]) -> None:
        with self._lock:
            self.total_classified += 1
            path = normalize_classification_path(result.get("source", "rules"))
            self.path_counts[path] += 1
            src = (result.get("source") or "rules").lower()
            self.source_counts[src] += 1

            if path == "rules_direct":
                self.rules_used += 1
            elif path == "rules_verified":
                self.semantic_used += 1
            elif path == "semantic_fallback":
                self.semantic_used += 1
            elif path == "groq_escalation":
                self.groq_used += 1
                self.semantic_used += 1
            else:
                self.rules_used += 1

            cat = result.get("category", "General")
            self.category_counts[cat] += 1
            self.confidence_sum += float(result.get("confidence", 0))

    def record_review_reason(self, reason: str) -> None:
        with self._lock:
            if reason:
                self.review_reason_counts[reason] += 1

    def record_skips(self, *, label_skipped: int = 0, dedup_skipped: int = 0) -> None:
        with self._lock:
            self.label_skipped += label_skipped
            self.dedup_skipped += dedup_skipped

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            n = self.total_classified or 1
            rules_direct = self.path_counts.get("rules_direct", 0)
            rules_verified = self.path_counts.get("rules_verified", 0)
            semantic_fb = self.path_counts.get("semantic_fallback", 0)
            groq = self.path_counts.get("groq_escalation", 0)
            llm_total = rules_verified + semantic_fb + groq
            review_flagged = sum(self.review_reason_counts.values())

            avg_rules_ms = (
                self._rules_latency_sum_ms / self._rules_latency_n
                if self._rules_latency_n
                else 0.0
            )
            avg_semantic_ms = (
                self._semantic_latency_sum_ms / self._semantic_latency_n
                if self._semantic_latency_n
                else 0.0
            )

            base = {
                "total_classified": self.total_classified,
                "rules_used": self.rules_used,
                "semantic_used": self.semantic_used,
                "groq_used": self.groq_used,
                "semantic_rate": round(self.semantic_used / n, 4),
                "groq_rate": round(self.groq_used / n, 4),
                "llm_rate": round(llm_total / n, 4),
                "rules_direct_rate": round(rules_direct / n, 4),
                "rules_verified_rate": round(rules_verified / n, 4),
                "semantic_fallback_rate": round(semantic_fb / n, 4),
                "review_queue_ratio": round(review_flagged / n, 4),
                "average_confidence": round(self.confidence_sum / n, 4),
                "label_skipped": self.label_skipped,
                "dedup_skipped": self.dedup_skipped,
                "category_distribution": dict(self.category_counts),
                "source_distribution": dict(self.source_counts),
                "classification_paths": dict(self.path_counts),
                "review_reason_breakdown": dict(self.review_reason_counts),
                "latency": {
                    "cycle_duration_ms": round(self.cycle_duration_ms, 1),
                    "total_cycle_ms": round(
                        self.total_cycle_ms or self.cycle_duration_ms, 1
                    ),
                    "gmail_list_ms": round(self.gmail_list_ms, 1),
                    "gmail_fetch_messages_ms": round(self.gmail_fetch_messages_ms, 1),
                    "gmail_fetch_labels_ms": round(self.gmail_fetch_labels_ms, 1),
                    "gmail_fetch_ms": round(self.gmail_fetch_ms, 1),
                    "filtering_ms": round(self.filtering_ms, 1),
                    "classify_ms": round(self.classify_ms, 1),
                    "classify_rules_ms": round(self.classify_rules_ms, 1),
                    "classify_semantic_ms": round(self.classify_semantic_ms, 1),
                    "actions_ms": round(self.actions_ms, 1),
                    "actions_apply_ms": round(self.actions_apply_ms, 1),
                    "db_write_ms": round(self.db_write_ms, 1),
                    "avg_rules_ms": round(avg_rules_ms, 1),
                    "avg_semantic_ms": round(avg_semantic_ms, 1),
                },
            }
        try:
            from backend.storage.corrections_store import corrections_store

            base.update(corrections_store.summary_counts())
        except Exception:
            pass
        try:
            from backend.infrastructure.gmail.gmail_transport import transport_metrics

            base["gmail_transport"] = transport_metrics.to_dict()
        except Exception:
            pass
        return base


metrics_store = ClassificationMetrics()
