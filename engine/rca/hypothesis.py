"""
RCA hypothesis generation based on correlated events, error propagation analysis, and multi-signal correlation patterns, with confidence scoring and severity categorization.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from api.responses import (
    MetricAnomaly, LogBurst, LogPattern,
    ServiceLatency, ErrorPropagation,
)
from engine.correlation.temporal import CorrelatedEvent
from engine.events.registry import DeploymentEvent, EventRegistry
from engine.topology.graph import DependencyGraph
from engine.rca.scoring import (
    score_correlated_event, score_deployment_correlation,
    score_error_propagation, categorize,
)
from engine.enums import Severity, RcaCategory
from config import settings


@dataclass
class RootCause:
    hypothesis: str
    confidence: float
    severity: Severity
    category: RcaCategory
    evidence: List[str] = field(default_factory=list)
    contributing_signals: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    recommended_action: str = ""
    deployment: Optional[DeploymentEvent] = None


def _signals_from_event(event: CorrelatedEvent) -> List[str]:
    signals: list[str] = []
    metric_names = list(dict.fromkeys(a.metric_name for a in event.metric_anomalies if a.metric_name))
    if metric_names:
        signals.extend([f"metric:{name}" for name in metric_names[:3]])
    if event.log_bursts:
        signals.append("log:bursts")
    latency_services = list(dict.fromkeys(s.service for s in event.service_latency if getattr(s, "service", None)))
    if latency_services:
        signals.extend([f"trace:{service}" for service in latency_services[:2]])
    if not signals:
        return ["metrics"]
    return signals


def _action_for_category(category: RcaCategory, service: str = "") -> str:
    actions = {
        RcaCategory.deployment:           f"Rollback recent deployment for {service or 'affected service'}.",
        RcaCategory.resource_exhaustion:  "Check resource limits, scale horizontally or increase quotas.",
        RcaCategory.dependency_failure:   "Inspect downstream dependencies and circuit breakers.",
        RcaCategory.traffic_surge:        "Verify rate limits, auto-scaling triggers, and CDN caching.",
        RcaCategory.error_propagation:    f"Isolate {service or 'source service'} and check recent changes.",
        RcaCategory.slo_burn:             "Immediate incident response; error budget critical.",
        RcaCategory.unknown:              "Review correlated signals and recent changes.",
    }
    return actions.get(category, "Investigate correlated signals.")


def generate(
    metric_anomalies: List[MetricAnomaly],
    log_bursts: List[LogBurst],
    log_patterns: List[LogPattern],
    service_latency: List[ServiceLatency],
    error_propagation: List[ErrorPropagation],
    correlated_events: Optional[List[CorrelatedEvent]] = None,
    graph: Optional[DependencyGraph] = None,
    event_registry: Optional[EventRegistry] = None,
) -> List[RootCause]:
    causes: List[RootCause] = []
    deployments = event_registry.list_all() if event_registry else []

    for event in (correlated_events or []):
        if event.confidence < settings.rca_event_confidence_threshold:
            continue

        category = categorize(event, deployments)
        base_score = score_correlated_event(event)
        deploy_score = score_deployment_correlation(event.window_start, deployments)
        confidence = round(min(settings.rca_score_cap, base_score + deploy_score * 0.2), 3)

        deploy_event: Optional[DeploymentEvent] = None
        nearby_deploys = [d for d in deployments if abs(d.timestamp - event.window_start) <= settings.rca_deploy_window_seconds]
        if nearby_deploys:
            deploy_event = min(nearby_deploys, key=lambda d: abs(d.timestamp - event.window_start))

        affected: List[str] = []
        root_svc = ""
        if event.service_latency and graph:
            root_svc = event.service_latency[0].service
            blast = graph.blast_radius(root_svc)
            affected = blast.affected_downstream

        metric_names = list({a.metric_name for a in event.metric_anomalies})[:2]
        svc_names = list({s.service for s in event.service_latency})[:2]

        parts = []
        if deploy_event:
            parts.append(f"deployment of {deploy_event.service} v{deploy_event.version}")
        if metric_names:
            parts.append(f"metric anomaly in {', '.join(metric_names)}")
        if svc_names:
            parts.append(f"latency spike in {', '.join(svc_names)}")
        if event.log_bursts:
            parts.append(f"{len(event.log_bursts)} log burst(s)")

        hypothesis = f"[{category.value}] Correlated incident: {' + '.join(parts) or 'multi-signal event'}"

        causes.append(RootCause(
            hypothesis=hypothesis,
            confidence=confidence,
            severity=Severity.from_score(confidence),
            category=category,
            evidence=[
                f"metrics={len(event.metric_anomalies)}",
                f"log_bursts={len(event.log_bursts)}",
                f"latency_services={len(event.service_latency)}",
            ],
            contributing_signals=_signals_from_event(event),
            affected_services=affected,
            recommended_action=_action_for_category(category, root_svc),
            deployment=deploy_event,
        ))

    for prop in error_propagation:
        svc = prop.source_service
        affected = getattr(prop, "affected_services", [])
        conf = score_error_propagation([prop])
        upstream = graph.find_upstream_roots(svc) if graph else []
        all_affected = list(dict.fromkeys(upstream + affected))
        causes.append(RootCause(
            hypothesis=f"[error_propagation] Errors originating from {svc}, cascading to {', '.join(affected[:3])}",
            confidence=conf,
            severity=Severity.high,
            category=RcaCategory.error_propagation,
            contributing_signals=[f"trace:propagation:{svc}"],
            affected_services=all_affected,
            recommended_action=_action_for_category(RcaCategory.error_propagation, svc),
        ))

    critical_patterns = [p for p in log_patterns if p.severity.weight() >= settings.rca_severity_weight_threshold]
    if critical_patterns:
        causes.append(RootCause(
            hypothesis=f"[log_pattern] {len(critical_patterns)} critical pattern(s): {critical_patterns[0].pattern[:80]}",
            confidence=settings.rca_log_pattern_score,
            severity=Severity.high,
            category=RcaCategory.unknown,
            contributing_signals=[f"log:{p.pattern[:40]}" for p in critical_patterns[:3]],
            recommended_action="Review high-severity log patterns for error root cause.",
        ))

    causes.sort(key=lambda c: c.confidence, reverse=True)
    min_conf = float(settings.rca_min_confidence_display)
    filtered = [cause for cause in causes if cause.confidence >= min_conf]
    if filtered:
        return filtered
    if causes:
        top = causes[0]
        top.hypothesis = f"[low_confidence] {top.hypothesis}"
        return [top]
    return causes
