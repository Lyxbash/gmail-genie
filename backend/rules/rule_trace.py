"""
Optional per-email rule trace for debugging classification.

Enable: set environment variable ``RULE_TRACE=1`` or pass ``trace=True``
to ``classify_by_rules``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from backend.rules.scoring import CategoryScore

_log = logging.getLogger(__name__)


def trace_enabled(explicit: bool = False) -> bool:
    if explicit:
        return True
    return os.getenv("RULE_TRACE", "").strip().lower() in ("1", "true", "yes")


class RuleTrace:
    """Collects stage results and per-category scores for one email."""

    def __init__(self, sender: str, subject: str) -> None:
        self.sender = sender
        self.subject = subject
        self.stages: List[Dict[str, Any]] = []
        self.category_scores: Dict[str, Dict[str, Any]] = {}
        self.final: Optional[Dict[str, Any]] = None

    def record_stage(self, stage: str, result: Optional[dict]) -> None:
        self.stages.append(
            {
                "stage": stage,
                "category": result.get("category") if result else None,
                "confidence": result.get("confidence") if result else None,
                "reason": result.get("reason") if result else None,
            }
        )

    def record_scores(self, scores: Dict[str, CategoryScore]) -> None:
        for cat, cs in scores.items():
            self.category_scores[cat] = {
                "score": cs.score,
                "positive": list(cs.positive_signals),
                "negative": list(cs.negative_signals),
            }

    def set_final(self, result: dict) -> None:
        self.final = result

    def format_report(self) -> str:
        lines = [
            "[EMAIL]",
            f"sender={self.sender}",
            f"subject={self.subject}",
            "",
        ]
        for stage in self.stages:
            name = stage["stage"].upper().replace("_", " ")
            if stage["category"]:
                lines.append(
                    f"[{name}] category={stage['category']} "
                    f"confidence={stage['confidence']:.2f} reason={stage['reason']}"
                )
            else:
                lines.append(f"[{name}] skipped")

        if self.category_scores:
            lines.append("")
            ranked = sorted(
                self.category_scores.items(),
                key=lambda x: x[1]["score"],
                reverse=True,
            )
            for cat, data in ranked:
                if data["score"] == 0 and not data["positive"] and not data["negative"]:
                    continue
                lines.append(
                    f"[{cat.upper()} RULE] score={data['score']} "
                    f"matched={data['positive']!r} "
                    f"negative={data['negative']!r}"
                )

        if self.final:
            lines.extend(
                [
                    "",
                    "[FINAL]",
                    f"category={self.final.get('category')}",
                    f"confidence={self.final.get('confidence')}",
                    f"reason={self.final.get('reason')}",
                ]
            )
        return "\n".join(lines)

    def emit(self) -> None:
        report = self.format_report()
        _log.debug("%s", report)
