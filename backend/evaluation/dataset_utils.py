"""
Shared helpers for evaluation dataset read/write.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = EVAL_DIR / "emails.json"

REQUIRED_FIELDS = frozenset({"sender", "subject", "expected_category"})


def normalize_field(text: str) -> str:
    """Collapse whitespace; preserve UTF-8 text."""
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", str(text).strip())
    return cleaned


def row_dedup_key(row: Dict[str, str]) -> str:
    return "|".join(
        [
            normalize_field(row.get("sender", "")).lower(),
            normalize_field(row.get("subject", "")).lower(),
            normalize_field(row.get("snippet", "")).lower()[:200],
            normalize_field(row.get("expected_category", "")).lower(),
        ]
    )


def normalize_row(raw: Dict[str, Any]) -> Dict[str, str]:
    return {
        "sender": normalize_field(str(raw.get("sender", ""))),
        "subject": normalize_field(str(raw.get("subject", ""))),
        "snippet": normalize_field(str(raw.get("snippet", ""))),
        "expected_category": normalize_field(str(raw.get("expected_category", ""))),
    }


def load_dataset(path: Path = DEFAULT_DATASET) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Dataset must be a JSON array")
    rows: List[Dict[str, str]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Row {i} must be an object")
        missing = REQUIRED_FIELDS - set(item.keys())
        if missing:
            raise ValueError(f"Row {i} missing: {sorted(missing)}")
        rows.append(normalize_row(item))
    return rows


def save_dataset(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")


def append_row(
    path: Path,
    *,
    sender: str,
    subject: str,
    snippet: str,
    expected_category: str,
) -> Tuple[bool, str]:
    """
    Append one row. Returns (added, message).
    ``added`` is False when an obvious duplicate exists.
    """
    new_row = normalize_row(
        {
            "sender": sender,
            "subject": subject,
            "snippet": snippet,
            "expected_category": expected_category,
        }
    )
    rows = load_dataset(path) if path.is_file() else []
    key = row_dedup_key(new_row)
    for existing in rows:
        if row_dedup_key(existing) == key:
            return False, "duplicate_skipped"
    rows.append(new_row)
    save_dataset(path, rows)
    return True, "appended"
