from __future__ import annotations

from typing import List

from engine.correlation.temporal import CorrelatedEvent
from engine.events.registry import DeploymentEvent
from engine.enums import RcaCategory


def score_deployment_correlation(
    anomaly_ts: float,
    deployments: List[DeploymentEvent],
    window_seconds: float = 300.0,
) -> float:
    nearby = [d for d in deployments if abs(d.timestamp - anomaly_ts) <= window_seconds]
    if not nearby:
        return 0.0
    closest_lag = min(abs(d.timestamp - anomaly_ts) for d in nearby)
    return round(max(0.0, 1.0 - closest_lag / window_seconds), 3)


def score_error_propagation(propagation: list) -> float:
    if not propagation:
        return 0.0
    affected = sum(len(getattr(p, "affected_services", [])) for p in propagation)
    return round(min(0.95, 0.5 + affected * 0.1), 3)


def score_correlated_event(event: CorrelatedEvent) -> float:
    weights = {
        "metrics": 0.25 * min(1.0, len(event.metric_anomalies)),
        "logs":    0.40 * min(1.0, len(event.log_bursts)),
        "traces":  0.35 * min(1.0, len(event.service_latency)),
    }
    return round(min(1.0, sum(weights.values())), 3)


def categorize(
    event: CorrelatedEvent,
    deployments: List[DeploymentEvent],
) -> RcaCategory:
    deploy_score = score_deployment_correlation(
        event.window_start, deployments
    ) if deployments else 0.0

    if deploy_score > 0.6:
        return RcaCategory.deployment

    has_memory = any(
        "memory" in a.metric_name or "mem" in a.metric_name
        for a in event.metric_anomalies
    )
    has_cpu = any("cpu" in a.metric_name for a in event.metric_anomalies)
    if has_memory or has_cpu:
        return RcaCategory.resource_exhaustion

    if event.service_latency:
        return RcaCategory.dependency_failure

    has_traffic = any(
        "request" in a.metric_name or "rate" in a.metric_name
        for a in event.metric_anomalies
    )
    if has_traffic:
        return RcaCategory.traffic_surge

    return RcaCategory.unknown