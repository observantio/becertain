from __future__ import annotations

from typing import Any, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field, model_serializer
from engine.enums import ChangeType, Severity, Signal


def _coerce(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _coerce(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class NpModel(BaseModel):
    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> Any:
        return _coerce(handler(self))


class MetricAnomaly(NpModel):
    metric_name: str
    timestamp: float
    value: float
    change_type: ChangeType
    z_score: float
    mad_score: float
    isolation_score: float
    expected_range: Tuple[float, float]
    severity: Severity
    description: str


class LogBurst(NpModel):
    window_start: float
    window_end: float
    rate_per_second: float
    baseline_rate: float
    ratio: float
    severity: Severity


class LogPattern(NpModel):
    pattern: str
    count: int
    first_seen: float
    last_seen: float
    rate_per_minute: float
    entropy: float
    severity: Severity
    sample: str


class ServiceLatency(NpModel):
    service: str
    operation: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    apdex: float
    error_rate: float
    sample_count: int
    severity: Severity


class ErrorPropagation(NpModel):
    source_service: str
    affected_services: List[str]
    error_rate: float
    severity: Severity


class RootCause(NpModel):
    hypothesis: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str]
    contributing_signals: List[Signal]
    recommended_action: str
    severity: Severity


class SloBurnAlert(NpModel):
    service: str
    window_label: str
    error_rate: float
    burn_rate: float
    budget_consumed_pct: float
    severity: Severity


class BudgetStatus(NpModel):
    service: str
    target_availability: float
    current_availability: float
    budget_used_pct: float
    remaining_minutes: float
    on_track: bool


class AnalysisReport(NpModel):
    tenant_id: str
    start: int
    end: int
    duration_seconds: int
    metric_anomalies: List[MetricAnomaly]
    log_bursts: List[LogBurst]
    log_patterns: List[LogPattern]
    service_latency: List[ServiceLatency]
    error_propagation: List[ErrorPropagation]
    slo_alerts: List[SloBurnAlert] = []
    root_causes: List[RootCause]
    ranked_causes: List[Any] = []
    change_points: List[Any] = []
    log_metric_links: List[Any] = []
    forecasts: List[Any] = []
    degradation_signals: List[Any] = []
    anomaly_clusters: List[Any] = []
    granger_results: List[Any] = []
    bayesian_scores: List[Any] = []
    overall_severity: Severity
    summary: str