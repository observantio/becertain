from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from engine.rca.hypothesis import RootCause
from engine.correlation.temporal import CorrelatedEvent


@dataclass(frozen=True)
class RankedCause:
    root_cause: RootCause
    ml_score: float
    final_score: float
    feature_importance: dict[str, float]


def _extract_features(cause: RootCause, event: Optional[CorrelatedEvent] = None) -> List[float]:
    return [
        cause.confidence,
        cause.severity.weight() / 8.0,
        len(cause.contributing_signals) / 10.0,
        len(cause.affected_services) / 10.0,
        1.0 if cause.deployment is not None else 0.0,
        len(event.metric_anomalies) / 5.0 if event else 0.0,
        len(event.log_bursts) / 5.0 if event else 0.0,
        len(event.service_latency) / 5.0 if event else 0.0,
        event.confidence if event else 0.0,
    ]


_FEATURE_NAMES = [
    "rule_confidence", "severity_weight", "signal_count",
    "blast_radius", "has_deployment", "metric_anomaly_count",
    "log_burst_count", "latency_count", "correlation_confidence",
]


def rank(
    causes: List[RootCause],
    correlated_events: Optional[List[CorrelatedEvent]] = None,
) -> List[RankedCause]:
    if not causes:
        return []

    events_map: dict[str, CorrelatedEvent] = {}
    if correlated_events:
        for ev in correlated_events:
            for a in ev.metric_anomalies:
                events_map[a.metric_name] = ev

    feature_matrix = []
    event_refs: List[Optional[CorrelatedEvent]] = []
    for cause in causes:
        ref_metric = next(
            (s.split(":")[1] for s in cause.contributing_signals if s.startswith("metric:")),
            None,
        )
        ev = events_map.get(ref_metric) if ref_metric else None
        event_refs.append(ev)
        feature_matrix.append(_extract_features(cause, ev))

    X = np.array(feature_matrix, dtype=float)

    try:
        from sklearn.ensemble import RandomForestClassifier

        if len(causes) >= 4:
            labels = [1 if c.confidence >= 0.5 else 0 for c in causes]
            if len(set(labels)) > 1:
                rf = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)
                rf.fit(X, labels)
                ml_scores = rf.predict_proba(X)[:, 1]
                importances = dict(zip(_FEATURE_NAMES, rf.feature_importances_))
            else:
                ml_scores = np.array([c.confidence for c in causes])
                importances = {n: 1.0 / len(_FEATURE_NAMES) for n in _FEATURE_NAMES}
        else:
            ml_scores = np.array([c.confidence for c in causes])
            importances = {n: 1.0 / len(_FEATURE_NAMES) for n in _FEATURE_NAMES}
    except ImportError:
        ml_scores = np.array([c.confidence for c in causes])
        importances = {n: 1.0 / len(_FEATURE_NAMES) for n in _FEATURE_NAMES}

    results: List[RankedCause] = []
    for cause, ml_score in zip(causes, ml_scores):
        final = round(0.6 * cause.confidence + 0.4 * float(ml_score), 3)
        results.append(RankedCause(
            root_cause=cause,
            ml_score=round(float(ml_score), 3),
            final_score=final,
            feature_importance=importances,
        ))

    return sorted(results, key=lambda r: r.final_score, reverse=True)