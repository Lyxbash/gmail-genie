"""
Gmail API transport error classification, backoff, and session metrics.
"""

from __future__ import annotations

import logging
import random
import re
import ssl
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)

MAX_FETCH_CONCURRENCY = 5
DEFAULT_FETCH_CONCURRENCY = 3

# SSL storm: abort parallel fetches if this many SSL errors in one batch window.
SSL_STORM_THRESHOLD = 5


class TransportErrorKind(str, Enum):
    SSL = "ssl_transport_error"
    TIMEOUT = "read_timeout"
    RATE_LIMIT = "http_429"
    CONNECTION_RESET = "connection_reset"
    TRANSPORT = "transport_corruption"
    HTTP = "http_error"
    OTHER = "other"


_SSL_MARKERS = (
    "wrong version number",
    "decryption failed",
    "bad record mac",
    "ssl",
    "tls",
    "certificate",
    "handshake",
)


def clamp_fetch_concurrency(value: int) -> int:
    return max(1, min(int(value), MAX_FETCH_CONCURRENCY))


def classify_transport_error(exc: BaseException) -> TransportErrorKind:
    if isinstance(exc, TimeoutError):
        return TransportErrorKind.TIMEOUT
    if isinstance(exc, ssl.SSLError):
        return TransportErrorKind.SSL
    msg = str(exc).lower()
    if "timed out" in msg or "timeout" in msg:
        return TransportErrorKind.TIMEOUT
    if "429" in msg or "rate limit" in msg or "userratelimit" in msg:
        return TransportErrorKind.RATE_LIMIT
    if "connection reset" in msg or "connection aborted" in msg:
        return TransportErrorKind.CONNECTION_RESET
    if any(m in msg for m in _SSL_MARKERS):
        return TransportErrorKind.SSL
    if "decryption" in msg or "wrong version" in msg:
        return TransportErrorKind.SSL
    try:
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            status = getattr(exc.resp, "status", None)
            if status == 429:
                return TransportErrorKind.RATE_LIMIT
            return TransportErrorKind.HTTP
    except ImportError:
        pass
    return TransportErrorKind.OTHER


def max_retries_for_kind(kind: TransportErrorKind) -> int:
    if kind == TransportErrorKind.RATE_LIMIT:
        return 5
    if kind == TransportErrorKind.SSL:
        return 4
    if kind == TransportErrorKind.TIMEOUT:
        return 4
    if kind == TransportErrorKind.CONNECTION_RESET:
        return 4
    return 3


def backoff_seconds(attempt: int, kind: TransportErrorKind) -> float:
    """Exponential backoff with jitter: 1s, 2s, 4s (+ jitter)."""
    base = min(2 ** (attempt - 1), 8)
    if kind == TransportErrorKind.RATE_LIMIT:
        base = min(2 ** attempt, 32)
    jitter = random.uniform(0, 0.4 * base)
    return base + jitter


@dataclass
class GmailTransportMetrics:
    """Per-process Gmail transport counters (reset at cycle start)."""

    retry_count: int = 0
    ssl_error_count: int = 0
    timeout_count: int = 0
    rate_limit_count: int = 0
    connection_reset_count: int = 0
    transport_corruption_count: int = 0
    partial_fetch_failures: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset_cycle(self) -> None:
        with self._lock:
            self.retry_count = 0
            self.ssl_error_count = 0
            self.timeout_count = 0
            self.rate_limit_count = 0
            self.connection_reset_count = 0
            self.transport_corruption_count = 0
            self.partial_fetch_failures = 0

    def record_retry(self, kind: TransportErrorKind) -> None:
        with self._lock:
            self.retry_count += 1
            if kind == TransportErrorKind.SSL:
                self.ssl_error_count += 1
            elif kind == TransportErrorKind.TIMEOUT:
                self.timeout_count += 1
            elif kind == TransportErrorKind.RATE_LIMIT:
                self.rate_limit_count += 1
            elif kind == TransportErrorKind.CONNECTION_RESET:
                self.connection_reset_count += 1
            elif kind in (TransportErrorKind.TRANSPORT, TransportErrorKind.OTHER):
                self.transport_corruption_count += 1

    def record_partial_failures(self, count: int) -> None:
        with self._lock:
            self.partial_fetch_failures += int(count)

    def to_dict(self) -> Dict[str, int]:
        with self._lock:
            return {
                "gmail_retry_count": self.retry_count,
                "gmail_ssl_error_count": self.ssl_error_count,
                "gmail_timeout_count": self.timeout_count,
                "gmail_rate_limit_count": self.rate_limit_count,
                "gmail_connection_reset_count": self.connection_reset_count,
                "gmail_transport_corruption_count": self.transport_corruption_count,
                "partial_fetch_failures": self.partial_fetch_failures,
            }


transport_metrics = GmailTransportMetrics()


def log_retry(
    *,
    attempt: int,
    max_attempts: int,
    kind: TransportErrorKind,
    delay: float,
    message_id: Optional[str] = None,
    exc: Optional[BaseException] = None,
) -> None:
    _log.warning(
        "[GMAIL RETRY] attempt=%d/%d error=%s backoff_seconds=%.1f message_id=%s detail=%s",
        attempt,
        max_attempts,
        kind.value,
        delay,
        message_id or "-",
        (str(exc)[:200] if exc else ""),
    )


@dataclass
class FetchBatchResult:
    emails: List[Dict[str, Any]]
    failed_ids: List[str]
    requested: int
    succeeded: int
    failed: int
    elapsed_ms: float
    aborted_early: bool = False
