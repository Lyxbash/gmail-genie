#!/usr/bin/env python3
"""
Offline classifier evaluation against backend/evaluation/emails.json.

Usage (from project root):
  python backend/evaluation/evaluate_classifier.py
  python backend/evaluation/evaluate_classifier.py --full
  python backend/evaluation/evaluate_classifier.py --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import yaml

from backend.evaluation.dataset_utils import DEFAULT_DATASET, load_dataset
from backend.rules.rule_engine import classify_by_rules

CONFIG_PATH = _PROJECT_ROOT / "config.yaml"
EVAL_DIR = Path(__file__).resolve().parent
LAST_EVAL_PATH = EVAL_DIR / "last_eval.json"
FAILURES_PATH = EVAL_DIR / "failures.json"


def _classify_rules(row: Dict[str, str]) -> Dict[str, Any]:
    return classify_by_rules(
        sender=row["sender"],
        subject=row["subject"],
        body_snippet=row.get("snippet", ""),
    )


def _classify_full(row: Dict[str, str]) -> Dict[str, Any]:
    from backend.services.classifier_service import EmailClassifier

    clf = EmailClassifier()
    email = {
        "sender": row["sender"],
        "subject": row["subject"],
        "snippet": row.get("snippet", ""),
        "body": row.get("snippet", ""),
    }
    return clf.classify_email(email)


def _per_category_metrics(
    results: List[Dict[str, Any]],
    categories: List[str],
) -> Dict[str, Dict[str, Any]]:
    metrics: Dict[str, Dict[str, Any]] = {}
    for cat in categories:
        tp = sum(
            1
            for r in results
            if r["expected_category"] == cat and r["predicted_category"] == cat
        )
        fp = sum(
            1
            for r in results
            if r["expected_category"] != cat and r["predicted_category"] == cat
        )
        fn = sum(
            1
            for r in results
            if r["expected_category"] == cat and r["predicted_category"] != cat
        )
        support = sum(1 for r in results if r["expected_category"] == cat)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        error_rate = fn / support if support else 0.0
        metrics[cat] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "error_rate": round(error_rate, 4),
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    return metrics


def _confusion_matrix(results: List[Dict[str, Any]]) -> Dict[str, int]:
    confusion: Counter[str] = Counter()
    for r in results:
        if r["expected_category"] != r["predicted_category"]:
            key = f"{r['expected_category']} -> {r['predicted_category']}"
            confusion[key] += 1
    return dict(confusion.most_common())


def _semantic_groq_rates(results: List[Dict[str, Any]]) -> Tuple[float, float]:
    n = len(results) or 1
    semantic = sum(
        1
        for r in results
        if (r.get("source") or "").lower()
        in ("semantic", "rules_verified", "groq_escalation")
    )
    groq = sum(
        1 for r in results if (r.get("source") or "").lower() == "groq_escalation"
    )
    return round(semantic / n, 4), round(groq / n, 4)


def _category_rankings(
    per_category: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Precision/recall rankings and hardest categories (support > 0)."""
    supported = {
        cat: m for cat, m in per_category.items() if m.get("support", 0) > 0
    }
    if not supported:
        return {
            "top_precision": [],
            "worst_precision": [],
            "top_recall": [],
            "worst_recall": [],
            "hardest_categories": [],
            "highest_confusion_categories": [],
        }

    by_precision = sorted(
        supported.items(), key=lambda x: x[1]["precision"], reverse=True
    )
    by_recall = sorted(supported.items(), key=lambda x: x[1]["recall"], reverse=True)
    by_error = sorted(
        supported.items(), key=lambda x: x[1]["error_rate"], reverse=True
    )

    def _fmt_rank(items: List[Tuple[str, Dict[str, Any]]], field: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for cat, m in items:
            val = m[field]
            out.append(
                {
                    "category": cat,
                    field: val,
                    f"{field}_percent": round(float(val) * 100, 1),
                    "support": m["support"],
                }
            )
        return out

    top_precision = _fmt_rank(by_precision[:8], "precision")
    worst_precision = _fmt_rank(
        sorted(supported.items(), key=lambda x: x[1]["precision"])[:8],
        "precision",
    )
    top_recall = _fmt_rank(by_recall[:8], "recall")
    worst_recall = _fmt_rank(
        sorted(supported.items(), key=lambda x: x[1]["recall"])[:8],
        "recall",
    )

    hardest = [
        {
            "category": cat,
            "error_rate": m["error_rate"],
            "error_rate_percent": round(m["error_rate"] * 100, 1),
            "fn": m["fn"],
            "support": m["support"],
        }
        for cat, m in by_error[:8]
        if m["fn"] > 0
    ]

    confusion_cats: Counter[str] = Counter()
    for cat, m in supported.items():
        if m["fn"] > 0:
            confusion_cats[cat] += m["fn"]

    return {
        "top_precision": top_precision,
        "worst_precision": worst_precision,
        "top_recall": top_recall,
        "worst_recall": worst_recall,
        "hardest_categories": hardest,
        "highest_confusion_categories": [
            {"category": cat, "misclassified_count": cnt}
            for cat, cnt in confusion_cats.most_common(8)
        ],
    }


def _export_failures(failures: List[Dict[str, Any]], path: Path) -> None:
    payload = [
        {
            "sender": f["sender"],
            "subject": f["subject"],
            "predicted": f["predicted_category"],
            "expected": f["expected_category"],
            "confidence": f["confidence"],
            "source": f.get("source", "rules"),
        }
        for f in failures
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_evaluation(
    *,
    dataset_path: Path,
    full_classifier: bool,
    limit: Optional[int],
    save_report: bool,
    export_failures: bool,
) -> Dict[str, Any]:
    rows = load_dataset(dataset_path)
    if limit is not None:
        rows = rows[:limit]

    classify_fn = _classify_full if full_classifier else _classify_rules
    mode = "full" if full_classifier else "rules_only"

    results: List[Dict[str, Any]] = []
    for row in rows:
        out = classify_fn(row)
        predicted = out.get("category", "General")
        results.append(
            {
                "sender": row["sender"],
                "subject": row["subject"],
                "expected_category": row["expected_category"],
                "predicted_category": predicted,
                "source": out.get("source", "rules"),
                "confidence": float(out.get("confidence", 0)),
                "correct": predicted == row["expected_category"],
            }
        )

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    incorrect = total - correct
    accuracy = round(correct / total, 4) if total else 0.0

    with CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    categories = sorted(
        set(cfg.get("categories", []))
        | {r["expected_category"] for r in results}
        | {r["predicted_category"] for r in results}
    )
    per_category = _per_category_metrics(results, categories)
    confusion = _confusion_matrix(results)
    semantic_rate, groq_rate = _semantic_groq_rates(results)
    rankings = _category_rankings(per_category)

    failures = [r for r in results if not r["correct"]]
    failures.sort(key=lambda r: r["confidence"], reverse=True)
    top_failures = failures[:15]

    if export_failures:
        _export_failures(failures, FAILURES_PATH)

    report: Dict[str, Any] = {
        "mode": mode,
        "dataset": str(dataset_path),
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": accuracy,
        "accuracy_percent": round(accuracy * 100, 2),
        "per_category": per_category,
        "category_rankings": rankings,
        "confusion": confusion,
        "semantic_rate": semantic_rate,
        "semantic_rate_percent": round(semantic_rate * 100, 2),
        "groq_rate": groq_rate,
        "groq_rate_percent": round(groq_rate * 100, 2),
        "top_failures": top_failures,
        "failures_export": str(FAILURES_PATH) if export_failures else None,
    }

    if save_report:
        LAST_EVAL_PATH.write_text(
            json.dumps(
                {
                    "confusion": confusion,
                    "accuracy": accuracy,
                    "mode": mode,
                    "total": total,
                    "category_rankings": rankings,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return report


def _print_report(report: Dict[str, Any]) -> None:
    print("=" * 60)
    print(f"Gmail Genie Evaluation ({report['mode']})")
    print("=" * 60)
    print(f"Dataset: {report['dataset']}")
    print(f"Total:   {report['total']}")
    print(f"Correct: {report['correct']}")
    print(f"Wrong:   {report['incorrect']}")
    print(f"Accuracy: {report['accuracy_percent']}%")
    print()
    print("Per-category (support > 0):")
    for cat, m in sorted(report["per_category"].items()):
        if m["support"] == 0:
            continue
        print(
            f"  {cat:32} precision={m['precision']:.2f} "
            f"recall={m['recall']:.2f} support={m['support']}"
        )
    rankings = report.get("category_rankings") or {}
    print()
    print("Top Precision:")
    for i, item in enumerate(rankings.get("top_precision", [])[:5], 1):
        print(
            f"  {i}. {item['category']} — {item.get('precision_percent', 0)}%"
        )
    print("Worst Recall:")
    for i, item in enumerate(rankings.get("worst_recall", [])[:5], 1):
        print(
            f"  {i}. {item['category']} — {item.get('recall_percent', 0)}%"
        )
    print()
    print("Hardest categories (by error rate):")
    for item in rankings.get("hardest_categories", [])[:5]:
        print(
            f"  {item['category']}: {item.get('error_rate_percent', 0)}% "
            f"({item['fn']}/{item['support']} wrong)"
        )
    print()
    print("Confusion (expected -> predicted):")
    if not report["confusion"]:
        print("  (none)")
    else:
        for pair, cnt in report["confusion"].items():
            print(f"  {pair}: {cnt}")
    print()
    print(
        f"Semantic used: {report['semantic_rate_percent']}%  "
        f"Groq used: {report['groq_rate_percent']}%"
    )
    if report.get("failures_export"):
        print(f"Failures exported: {report['failures_export']}")
    print()
    print("Top failures:")
    if not report["top_failures"]:
        print("  (none)")
    else:
        for f in report["top_failures"]:
            print(
                f"  - expected={f['expected_category']} "
                f"predicted={f['predicted_category']}"
            )
            print(f"    sender={f['sender'][:70]}")
            print(f"    subject={f['subject'][:70]}")
            print(
                f"    source={f['source']} confidence={f['confidence']:.2f}"
            )
    print("=" * 60)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Gmail Genie classifier")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full hybrid classifier (may invoke Ollama/Groq)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write last_eval.json for /confusion-report",
    )
    parser.add_argument(
        "--no-failures-export",
        action="store_true",
        help="Do not write failures.json",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report only")
    args = parser.parse_args(argv)

    report = run_evaluation(
        dataset_path=args.dataset,
        full_classifier=args.full,
        limit=args.limit,
        save_report=not args.no_save,
        export_failures=not args.no_failures_export,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report)
    return 0 if report["incorrect"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
