"""
Merge confusion pairs from offline evaluation and user corrections.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict

from backend.storage.corrections_store import corrections_store

LAST_EVAL_PATH = Path(__file__).resolve().parent / "last_eval.json"


def build_confusion_report() -> Dict[str, int]:
    merged: Counter[str] = Counter()

    if LAST_EVAL_PATH.is_file():
        try:
            data = json.loads(LAST_EVAL_PATH.read_text(encoding="utf-8"))
            for key, cnt in (data.get("confusion") or {}).items():
                merged[key] += int(cnt)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    for key, cnt in corrections_store.confusion_from_corrections().items():
        merged[key] += int(cnt)

    return dict(merged.most_common())
