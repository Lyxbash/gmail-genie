"""
Shared API response models for dashboard and operations endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EmailClassification(BaseModel):
    message_id: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    snippet: Optional[str] = None
    category: str
    confidence: float
    source: str = "rules"
    action_applied: bool = False
    score_margin: Optional[int] = None
    review_reason: Optional[str] = None


class ActivityItem(BaseModel):
    message_id: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    category: str
    confidence: float
    source: str = "rules"
    action_applied: bool = False
    score_margin: Optional[int] = None
    created_at: str


class ReviewQueueItem(BaseModel):
    message_id: Optional[str] = None
    sender: str
    subject: str
    snippet: str = ""
    predicted_category: str
    confidence: float
    source: str = "rules"
    reason: str
    score_margin: Optional[int] = None
    top_score: Optional[int] = None
    second_category: Optional[str] = None


class MetricsSummary(BaseModel):
    total_classified: int = 0
    rules_used: int = 0
    semantic_used: int = 0
    groq_used: int = 0
    semantic_rate: float = 0.0
    groq_rate: float = 0.0
    average_confidence: float = 0.0
    label_skipped: int = 0
    dedup_skipped: int = 0
    category_distribution: Dict[str, int] = Field(default_factory=dict)
    source_distribution: Dict[str, int] = Field(default_factory=dict)
    corrections_count: int = 0
    sender_override_count: int = 0


class HistoricalTotals(BaseModel):
    total_processed: int = 0
    total_label_skipped: int = 0
    total_semantic_calls: int = 0
    total_groq_calls: int = 0
    total_corrections: int = 0


class CurrentCycleSnapshot(BaseModel):
    pages_scanned: int = 0
    fetched_total: int = 0
    label_skipped: int = 0
    dedup_skipped: int = 0
    classified: int = 0
    actions_applied: int = 0
    cycle_duration_ms: float = 0.0
    dry_run: bool = False
    completed_at: Optional[str] = None
    started_at: Optional[str] = None
    latency: Dict[str, float] = Field(default_factory=dict)
    running: bool = False
    current_stage: str = "idle"
    cycle_state: str = "idle"
    partial_fetch_failures: int = 0
    elapsed_seconds: Optional[float] = None
    heartbeat_stale: bool = False


class DashboardOverview(BaseModel):
    historical: HistoricalTotals = Field(default_factory=HistoricalTotals)
    current_cycle: CurrentCycleSnapshot = Field(default_factory=CurrentCycleSnapshot)
    last_successful_cycle: Optional[Dict[str, Any]] = None
    cycle_running: bool = False
    top_categories: Dict[str, int]
    recent_activity: List[ActivityItem]
    accuracy_estimate: Optional[float] = None
    session_metrics: Dict[str, Any] = Field(default_factory=dict)
    # Legacy flat fields (mirror historical for older clients)
    total_processed: int = 0
    label_skipped: int = 0
    semantic_used: int = 0
    groq_used: int = 0


class HealthStatus(BaseModel):
    status: str
    gmail_connected: bool
    ollama_available: bool
    groq_enabled: bool
    database_ok: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class ConfigSummary(BaseModel):
    provider: str
    model: str
    thresholds: Dict[str, float]
    limits: Dict[str, int]
    features: Dict[str, bool]
    categories: List[str]
