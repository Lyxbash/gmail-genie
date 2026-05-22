"""
Hybrid email classifier — deterministic rules first, semantic LLM fallback, rare Groq.

Pipeline:
  cache → rules (high/medium confidence) → Ollama semantic → optional Groq escalation
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import sqlite3
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.config import load_config
from backend.infrastructure.llm.rule_trust import (
    is_strong_rule_match,
    normalize_classification_path,
    promote_rule_confidence,
    should_skip_rule_verify,
    should_use_rule_verify,
)
from backend.rules.score_margin import compute_score_margin_for_email
from backend.infrastructure.llm.llm_providers import (
    BaseLLMProvider,
    create_groq_escalation_provider,
    create_primary_provider,
)
from backend.storage.metrics import metrics_store
from backend.rules.rule_engine import classify_by_rules
from backend.rules.scoring import has_transactional_block

from backend.paths import PROJECT_DATA_DIR

DATA_DIR = PROJECT_DATA_DIR
CACHE_DB = DATA_DIR / "cache.db"
DATA_DIR.mkdir(exist_ok=True)

config = load_config()
CATEGORIES: List[str] = config["categories"]
_llm = config.get("llm", {})

_log = logging.getLogger(__name__)

TEMPERATURE = float(_llm.get("temperature", 0.1))
BODY_PREVIEW_CHARS = int(_llm.get("body_preview_chars", 250))
RULE_HIGH_CONFIDENCE = float(_llm.get("rule_high_confidence", 0.95))
RULE_MEDIUM_CONFIDENCE = float(_llm.get("rule_medium_confidence", 0.70))
RULE_VERIFY_MAX_CONFIDENCE = float(_llm.get("rule_verify_max_confidence", 0.92))
SEMANTIC_ACCEPT_CONFIDENCE = float(_llm.get("semantic_accept_confidence", 0.70))
GROQ_ESCALATION_CONFIDENCE = float(_llm.get("groq_escalation_confidence", 0.55))
SEMANTIC_RETRIES = int(_llm.get("semantic_retries", 1))
GROQ_RETRIES = int(_llm.get("groq_retries", 1))
ESCALATION_ENABLED = bool(_llm.get("escalation_enabled", True))

TRANSACTIONAL_CATEGORIES: Set[str] = {"Security Alerts", "Receipts", "Finance"}
TRANSACTIONAL_OVERRIDE_MIN = 0.93
STALE_JOB_CATEGORIES: Set[str] = {
    "Job Alerts",
    "Job Applications/Referrals",
    "Recruiters",
}
GOOGLE_TXN_SENDER_MARKERS = (
    "googleplay-noreply",
    "googleone-noreply",
    "pay-noreply",
    "payments-noreply",
)

SEMANTIC_SYSTEM = (
    "Classify the email into exactly ONE category from the allowed list. "
    "Return ONLY valid JSON with keys category and confidence. No markdown."
)

RULE_VERIFY_ENABLED = bool(_llm.get("rule_verify_enabled", True))
RULE_VERIFY_MIN_CONFIDENCE = float(_llm.get("rule_verify_min_confidence", 0.72))
RULE_VERIFY_ACCEPT_CONFIDENCE = float(_llm.get("rule_verify_accept_confidence", 0.70))
RULE_TRUST_SHORT_CIRCUIT = float(_llm.get("rule_trust_short_circuit", 0.93))
SEMANTIC_MAX_CONCURRENCY = int(_llm.get("semantic_max_concurrency", 2))

RULE_VERIFY_SYSTEM = (
    "Validate the proposed email category. Return ONLY compact JSON. No markdown."
)
RULE_VERIFY_USER = """Email:
Sender: {sender}
Subject: {subject}
Snippet: {snippet}

Rule predicted: {rule_category}

Answer ONLY:
{{"agree": true, "better_category": "{rule_category}", "confidence": 0.88}}
or if wrong:
{{"agree": false, "better_category": "General", "confidence": 0.85}}
"""

SEMANTIC_USER = """Allowed categories: {categories}

Distinctions:
- Promotions: marketing, sales, discounts, webinars, campaigns, growth emails
- Newsletters: recurring editorial/informational digests, industry updates
- Job Alerts: ONLY hiring/job recommendations — NOT subscriptions, refunds, Play/One receipts, account setup, security codes, or newsletters
- Job Applications/Referrals: applied roles, interviews, assessments, referrals
- Recruiters: recruiter outreach and hiring conversations
- Social: networking, messages, invitations, connection requests
- Docs: shared files, Drive/Notion/Slack/collaboration tool notifications
- Finance: banking, bills, statements, payments (not product receipts)
- Receipts: order confirmations, invoices, payment receipts
- Shopping: shipping, delivery, order updates
- Security Alerts: OTP, login, password reset, account security

From: {sender}
Subject: {subject}
Snippet: {snippet}
{body_line}

Return ONLY:
{{"category":"...","confidence":0.91}}"""


def clean_email_body(text: str, max_chars: Optional[int] = None) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = re.sub(r"[\u200b-\u200d\ufeff]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if max_chars:
        cleaned = cleaned[:max_chars]
    return cleaned


def extract_json_from_llm(content: str) -> Dict[str, Any]:
    if not content:
        raise ValueError("empty response")
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no json object in response")
    return json.loads(text[start : end + 1])


def normalize_sender_domain(sender: str) -> str:
    _, addr = parseaddr((sender or "").lower())
    if "@" in addr:
        return addr.split("@")[-1]
    return (sender or "").lower()[:80]


def normalize_subject_pattern(subject: str) -> str:
    s = (subject or "").lower().strip()
    s = re.sub(r"^(re|fwd|fw):\s*", "", s)
    s = re.sub(r"\d{4}-\d{2}-\d{2}", "#date#", s)
    s = re.sub(r"\d+", "#", s)
    s = re.sub(r"\s+", " ", s)
    return s[:120]


class EmailClassifier:
    """Rules-first classifier with per-email semantic fallback."""

    def __init__(
        self,
        primary_provider: Optional[BaseLLMProvider] = None,
        escalation_provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        self.primary_provider = primary_provider or create_primary_provider(_llm)
        self.groq_provider = escalation_provider
        if self.groq_provider is None and ESCALATION_ENABLED:
            self.groq_provider = create_groq_escalation_provider(_llm)

        self._db_lock = threading.Lock()
        self.conn = sqlite3.connect(str(CACHE_DB), check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        with self._db_lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS classifications (
                    hash TEXT PRIMARY KEY,
                    result TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pattern_cache (
                    pattern_key TEXT PRIMARY KEY,
                    result TEXT
                )
                """
            )
            self.conn.commit()

    def _get_exact_cache(self, key: str) -> Optional[Dict]:
        with self._db_lock:
            cur = self.conn.cursor()
            cur.execute("SELECT result FROM classifications WHERE hash=?", (key,))
            row = cur.fetchone()
            return json.loads(row[0]) if row else None

    def _set_exact_cache(self, key: str, result: Dict) -> None:
        with self._db_lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO classifications (hash, result) VALUES (?, ?)",
                (key, json.dumps(result)),
            )
            self.conn.commit()

    def _get_pattern_cache(self, key: str) -> Optional[Dict]:
        with self._db_lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT result FROM pattern_cache WHERE pattern_key=?", (key,)
            )
            row = cur.fetchone()
            return json.loads(row[0]) if row else None

    def _set_pattern_cache(self, key: str, result: Dict) -> None:
        with self._db_lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO pattern_cache (pattern_key, result) VALUES (?, ?)",
                (key, json.dumps(result)),
            )
            self.conn.commit()

    def _exact_cache_key(self, email: Dict) -> str:
        raw = (
            normalize_sender_domain(email.get("sender", ""))
            + "|"
            + (email.get("subject", "") or "")[:200].lower()
            + "|"
            + (email.get("snippet", "") or "")[:200]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _pattern_cache_key(self, email: Dict) -> str:
        domain = normalize_sender_domain(email.get("sender", ""))
        pattern = normalize_subject_pattern(email.get("subject", ""))
        return hashlib.sha256(f"{domain}|{pattern}".encode()).hexdigest()

    def _validate(self, parsed: Dict) -> Dict:
        cat = parsed.get("category", "General")
        if cat not in CATEGORIES:
            cat = "General"
        try:
            conf = float(parsed.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        return {
            "category": cat,
            "confidence": max(0.0, min(conf, 1.0)),
        }

    def _run_rules(self, email: Dict) -> Dict:
        return classify_by_rules(
            sender=email.get("sender", ""),
            subject=email.get("subject", ""),
            body_snippet=email.get("snippet", ""),
        )

    def _is_stale_job_cache(self, cached: Dict, email: Dict) -> bool:
        """
        Detect cache entries from the old first-match job pipeline.

        Google Play/One and other transactional mail must not reuse Job labels.
        """
        if cached.get("category") not in STALE_JOB_CATEGORIES:
            return False
        sender_lower = (email.get("sender") or "").lower()
        if any(m in sender_lower for m in GOOGLE_TXN_SENDER_MARKERS):
            return True
        combined = " ".join(
            [
                sender_lower,
                (email.get("subject") or "").lower(),
                (email.get("snippet") or "").lower(),
            ]
        )
        return has_transactional_block(combined)

    def _body_preview(self, email: Dict) -> str:
        body = clean_email_body(email.get("body") or "", BODY_PREVIEW_CHARS)
        if not body:
            body = clean_email_body(email.get("snippet") or "", BODY_PREVIEW_CHARS)
        return body

    def _build_semantic_prompt(self, email: Dict) -> str:
        body = self._body_preview(email)
        body_line = f"Body preview: {body}" if body else ""
        return SEMANTIC_USER.format(
            categories=", ".join(CATEGORIES),
            sender=email.get("sender", ""),
            subject=email.get("subject", ""),
            snippet=(email.get("snippet") or "")[:400],
            body_line=body_line,
        )

    def _rule_verify(self, email: Dict, rules: Dict) -> Dict[str, Any]:
        proposed = rules.get("category", "General")
        user_prompt = RULE_VERIFY_USER.format(
            rule_category=proposed,
            sender=email.get("sender", ""),
            subject=email.get("subject", ""),
            snippet=(email.get("snippet") or "")[:300],
        )
        content = self.primary_provider.chat(
            RULE_VERIFY_SYSTEM,
            user_prompt,
            temperature=0.0,
        )
        parsed = extract_json_from_llm(content)
        agree = bool(parsed.get("agree", parsed.get("accept", False)))
        better = parsed.get("better_category", proposed)
        if better not in CATEGORIES:
            better = proposed if agree else "General"
        try:
            conf = float(parsed.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        return {
            "agree": agree,
            "better_category": better,
            "confidence": max(0.0, min(conf, 1.0)),
        }

    def _llm_classify(
        self,
        provider: BaseLLMProvider,
        user_prompt: str,
        retries: int,
        source: str,
    ) -> Dict:
        last_error: Optional[Exception] = None
        attempts = max(1, retries + 1)
        for _ in range(attempts):
            try:
                content = provider.chat(
                    SEMANTIC_SYSTEM, user_prompt, temperature=TEMPERATURE
                )
                parsed = extract_json_from_llm(content)
                out = self._validate(parsed)
                out["source"] = source
                out["llm_provider"] = provider.provider_name
                return out
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
            except TimeoutError:
                raise
            except Exception as exc:
                last_error = exc
        return {
            "category": "General",
            "confidence": 0.40,
            "reason": f"llm_failed: {last_error}",
            "source": source,
        }

    def _semantic_classify(self, email: Dict) -> Dict:
        user_prompt = self._build_semantic_prompt(email)
        return self._llm_classify(
            self.primary_provider,
            user_prompt,
            SEMANTIC_RETRIES,
            "semantic",
        )

    def _groq_escalate(self, email: Dict, cache_key: str) -> Dict:
        if not self.groq_provider:
            return {
                "category": "General",
                "confidence": 0.45,
                "reason": "groq_unavailable",
                "source": "fallback",
            }
        groq_key = hashlib.sha256((cache_key + ":groq").encode()).hexdigest()
        cached = self._get_exact_cache(groq_key)
        if cached:
            return cached
        user_prompt = self._build_semantic_prompt(email)
        result = self._llm_classify(
            self.groq_provider,
            user_prompt,
            GROQ_RETRIES,
            "groq_escalation",
        )
        self._set_exact_cache(groq_key, result)
        return result

    def _apply_transactional_override(self, semantic: Dict, rules: Dict) -> Dict:
        """Prefer high-confidence transactional rules over wrong semantic labels."""
        sc = semantic.get("category")
        rc = rules.get("category")
        sconf = float(semantic.get("confidence", 0))
        rconf = float(rules.get("confidence", 0))
        if (
            rc in TRANSACTIONAL_CATEGORIES
            and rconf >= TRANSACTIONAL_OVERRIDE_MIN
            and sc != rc
            and sc in (STALE_JOB_CATEGORIES | {"Promotions", "Newsletters", "General", "Shopping"})
        ):
            return {
                "category": rc,
                "confidence": rconf,
                "reason": f"transactional_override: {rules.get('reason', '')}",
                "source": "rules_override",
            }
        return semantic

    def _cache_result(self, exact_key: str, pattern_key: str, result: Dict) -> None:
        self._set_exact_cache(exact_key, result)
        self._set_pattern_cache(pattern_key, result)

    def _should_escalate_to_groq(self, semantic: Dict) -> bool:
        if not self.groq_provider:
            return False
        conf = float(semantic.get("confidence", 0))
        cat = semantic.get("category", "General")
        if conf < GROQ_ESCALATION_CONFIDENCE:
            return True
        if cat == "General" and conf < SEMANTIC_ACCEPT_CONFIDENCE:
            return True
        return False

    def classify_email(self, email: Dict) -> Dict:
        exact_key = self._exact_cache_key(email)
        pattern_key = self._pattern_cache_key(email)

        cached = self._get_exact_cache(exact_key)
        if cached and not self._is_stale_job_cache(cached, email):
            metrics_store.record_classification(cached)
            return cached

        pattern_cached = self._get_pattern_cache(pattern_key)
        if pattern_cached and not self._is_stale_job_cache(pattern_cached, email):
            self._set_exact_cache(exact_key, pattern_cached)
            metrics_store.record_classification(pattern_cached)
            return pattern_cached

        t0 = time.perf_counter()
        rules = self._run_rules(email)
        rules = promote_rule_confidence(rules)
        margin_info = compute_score_margin_for_email(
            email.get("sender", ""),
            email.get("subject", ""),
            email.get("snippet", ""),
        )
        metrics_store.record_rules_latency((time.perf_counter() - t0) * 1000)

        rcat = rules.get("category", "General")
        rconf = float(rules.get("confidence", 0))
        trusted = is_strong_rule_match(rules) or should_skip_rule_verify(rules, margin_info)
        sdom = normalize_sender_domain(email.get("sender", ""))
        _log.info(
            "[RULE MATCH] category=%s confidence=%.2f domain=%s trusted=%s reason=%s",
            rcat,
            rconf,
            sdom,
            trusted,
            rules.get("reason", ""),
        )

        def _finalize(out: Dict[str, Any], label: str) -> Dict[str, Any]:
            out = dict(out)
            out["source"] = normalize_classification_path(out.get("source", "rules"))
            if out["source"] == "rules":
                out["source"] = "rules_direct"
            out["classification_path"] = out["source"]
            out["rules_trusted"] = trusted or out["source"] == "rules_direct"
            out["score_margin"] = margin_info.get("score_margin")
            self._cache_result(exact_key, pattern_key, out)
            _log.info("[FINAL CATEGORY] %s (%s)", out["category"], label)
            metrics_store.record_classification(out)
            return out

        if rconf >= RULE_HIGH_CONFIDENCE or rconf >= RULE_TRUST_SHORT_CIRCUIT:
            return _finalize(
                {**rules, "source": "rules_direct"},
                "trusted_rule high",
            )

        if rcat != "General" and rconf >= RULE_MEDIUM_CONFIDENCE:
            if should_use_rule_verify(
                rules, margin_info, verify_enabled=RULE_VERIFY_ENABLED
            ):
                try:
                    _log.info(
                        "[RULE VERIFY] proposed=%s confidence=%.2f margin=%s",
                        rcat,
                        rconf,
                        margin_info.get("score_margin"),
                    )
                    t_v = time.perf_counter()
                    verdict = self._rule_verify(email, rules)
                    metrics_store.record_semantic_latency(
                        (time.perf_counter() - t_v) * 1000
                    )
                    ok = (
                        verdict["agree"]
                        and verdict["confidence"] >= RULE_VERIFY_ACCEPT_CONFIDENCE
                    )
                    if ok:
                        return _finalize(
                            {
                                **rules,
                                "category": verdict.get("better_category", rcat),
                                "source": "rules_verified",
                                "verifier_confidence": verdict["confidence"],
                            },
                            "verified",
                        )
                    _log.info(
                        "[VERIFY OVERRIDDEN] proposed=%s agree=%s better=%s",
                        rcat,
                        verdict.get("agree"),
                        verdict.get("better_category"),
                    )
                except TimeoutError:
                    _log.info("[RULE VERIFY] timeout, falling back to semantic")
                except Exception as exc:
                    _log.info("[RULE VERIFY] error=%s, falling back to semantic", exc)
            else:
                return _finalize(
                    {**rules, "source": "rules_direct"},
                    "trusted_rule medium",
                )

        try:
            _log.info("[SEMANTIC FALLBACK] after_rules category=%s conf=%.2f", rcat, rconf)
            t_s = time.perf_counter()
            semantic = self._semantic_classify(email)
            metrics_store.record_semantic_latency((time.perf_counter() - t_s) * 1000)
        except TimeoutError:
            semantic = {
                "category": rcat if rcat != "General" else "General",
                "confidence": max(rconf, 0.55),
                "reason": "semantic_timeout",
                "source": "fallback",
            }

        semantic = self._apply_transactional_override(semantic, rules)
        sconf = float(semantic.get("confidence", 0))

        if sconf >= SEMANTIC_ACCEPT_CONFIDENCE:
            return _finalize(semantic, "semantic")

        if self._should_escalate_to_groq(semantic):
            try:
                _log.info("[GROQ ESCALATION]")
                t_g = time.perf_counter()
                groq_result = self._groq_escalate(email, exact_key)
                metrics_store.record_semantic_latency((time.perf_counter() - t_g) * 1000)
                gconf = float(groq_result.get("confidence", 0))
                if gconf >= sconf or groq_result.get("category") != "General":
                    semantic = groq_result
            except (TimeoutError, Exception):
                pass

        return _finalize(semantic, "final")

    def batch_classify_emails(self, emails: List[Dict]) -> List[Dict]:
        """Classify emails with bounded concurrency (Ollama semaphore limits load)."""
        if not emails:
            return []
        workers = max(1, min(SEMANTIC_MAX_CONCURRENCY, len(emails)))
        if workers == 1:
            return [self.classify_email(email) for email in emails]

        results: List[Optional[Dict]] = [None] * len(emails)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.classify_email, email): i
                for i, email in enumerate(emails)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                results[idx] = fut.result()
        return [r for r in results if r is not None]
