#!/usr/bin/env python3
"""
Append labeled emails to backend/evaluation/emails.json.

Usage:
  python backend/evaluation/add_to_dataset.py \\
    --sender "TLDR <hello@tldrnewsletter.com>" \\
    --subject "DeepSeek v4" \\
    --snippet "..." \\
    --expected-category Newsletters
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.evaluation.dataset_utils import DEFAULT_DATASET, append_row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append email to evaluation dataset")
    parser.add_argument("--sender", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--snippet", default="")
    parser.add_argument("--expected-category", required=True, dest="expected_category")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args(argv)

    added, message = append_row(
        args.dataset,
        sender=args.sender,
        subject=args.subject,
        snippet=args.snippet,
        expected_category=args.expected_category,
    )
    result = {
        "ok": True,
        "added": added,
        "message": message,
        "dataset": str(args.dataset),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{message} ({'added' if added else 'skipped'}) -> {args.dataset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
