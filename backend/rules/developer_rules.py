"""
Developer, DevOps, and cloud platform classification rules.

Maps primarily to ``Work``; document-sharing signals map to ``Docs``.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import DEV_DOMAINS
from backend.rules.keyword_lists import DEVELOPER_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY_WORK = "Work"
CATEGORY_DOCS = "Docs"


def classify_developer(ctx: EmailContext) -> Optional[dict]:
    """Classify CI/CD, repos, cloud alerts, and dev tooling."""
    doc_signals = [
        "shared a document",
        "shared with you",
        "google docs",
        "google drive",
        "shared a file",
        "view document",
        "commented on",
        "mentioned you in",
        "figma.com",
        "notion.so",
    ]
    if contains_any(ctx.combined, doc_signals):
        return build_result(
            category=CATEGORY_DOCS,
            confidence=0.92,
            reason="matched_developer_doc_sharing",
        )

    if domain_matches(ctx.domain, DEV_DOMAINS):
        return build_result(
            category=CATEGORY_WORK,
            confidence=0.94,
            reason="matched_developer_domain",
        )

    if contains_any(ctx.combined, DEVELOPER_KEYWORDS):
        return build_result(
            category=CATEGORY_WORK,
            confidence=0.91,
            reason="matched_developer_keywords",
        )

    return None
