"""
Standardized rule classification results and email text utilities.

All rule modules must use ``build_result`` for consistent dict output
compatible with the hybrid classifier pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr
from typing import List, Optional, Tuple

_EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I)


RULE_SOURCE = "rules"


@dataclass(frozen=True)
class EmailContext:
    """Normalized email fields used across rule classifiers."""

    sender: str
    subject: str
    body_snippet: str
    sender_lower: str
    subject_lower: str
    body_lower: str
    combined: str
    domain: str


def normalize_text(text: str) -> str:
    """Lowercase and strip email text for deterministic matching."""
    return (text or "").strip().lower()


def _extract_email_address(sender: str) -> str:
    """Parse RFC From header; fall back to first email-like token in text."""
    sender_norm = normalize_text(sender)
    _, email_addr = parseaddr(sender_norm)
    email_addr = email_addr.strip().lower()
    if "@" in email_addr:
        return email_addr
    found = _EMAIL_IN_TEXT.search(sender_norm)
    if found:
        return found.group(0).lower()
    return ""


def extract_sender_domain(sender: str) -> str:
    """
    Extract the real mailbox domain from a From header (no substring hacks).

    Uses RFC parseaddr so display names do not pollute the hostname.
    """
    email_addr = _extract_email_address(sender)
    if "@" in email_addr:
        return email_addr.rsplit("@", 1)[-1]
    return ""


def extract_sender_mailbox(sender: str) -> Tuple[str, str]:
    """Return (local_part, domain) in lowercase, or ("", "") if not parseable."""
    email_addr = _extract_email_address(sender)
    if "@" not in email_addr:
        return "", ""
    local, _, host = email_addr.partition("@")
    return local.strip(), host.strip()


# Legacy name kept for call sites; identical to extract_sender_domain.
def extract_domain(sender: str) -> str:
    return extract_sender_domain(sender)


def contains_any(text: str, keywords: List[str]) -> bool:
    """Return True if any keyword appears as a substring in text."""
    return any(keyword in text for keyword in keywords)


def contains_word_any(text: str, keywords: List[str]) -> bool:
    """Word-boundary match for short tokens (avoids 'job' inside unrelated words)."""
    for kw in keywords:
        if len(kw) <= 4:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return True
        elif kw in text:
            return True
    return False


def hostname_matches_registry(hostname: str, registered_hosts: List[str]) -> bool:
    """
    Return True if hostname equals a registry entry or is its subdomain.

    Example: mail.google.com matches registry google.com;
    careers.google.com matches careers.google.com exactly.
    """
    h = (hostname or "").strip().lower()
    if not h:
        return False
    for reg in registered_hosts:
        r = (reg or "").strip().lower()
        if not r:
            continue
        if h == r or h.endswith("." + r):
            return True
    return False


def domain_matches(domain: str, domain_patterns: List[str]) -> bool:
    """
    Match sender domain against a list of registered hostnames.

    Uses exact host or subdomain-of-registry semantics — not naive substring.
    """
    return hostname_matches_registry(domain, domain_patterns)


def prepare_email_context(
    sender: str,
    subject: str,
    body_snippet: str = "",
    body_preview_chars: int = 200,
) -> EmailContext:
    """Build normalized context shared by all rule classifiers."""
    sender_lower = normalize_text(sender)
    subject_lower = normalize_text(subject)
    body_lower = normalize_text(body_snippet[:body_preview_chars])
    combined = f"{sender_lower} {subject_lower} {body_lower}"
    domain = extract_sender_domain(sender)
    return EmailContext(
        sender=sender or "",
        subject=subject or "",
        body_snippet=body_snippet or "",
        sender_lower=sender_lower,
        subject_lower=subject_lower,
        body_lower=body_lower,
        combined=combined,
        domain=domain,
    )


def build_result(
    category: str,
    confidence: float,
    reason: str,
    source: str = RULE_SOURCE,
) -> dict:
    confidence_clamped = max(0.0, min(float(confidence), 1.0))
    return {
        "category": category,
        "confidence": confidence_clamped,
        "reason": reason,
        "source": source,
    }


def merge_tags(
    result: dict,
    tags: Optional[List[str]] = None,
) -> dict:
    if tags:
        result = {**result, "tags": tags}
    return result
