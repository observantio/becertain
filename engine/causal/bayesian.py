from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from engine.enums import RcaCategory


_PRIORS: Dict[RcaCategory, float] = {
    RcaCategory.deployment:          0.35,
    RcaCategory.resource_exhaustion: 0.20,
    RcaCategory.dependency_failure:  0.20,
    RcaCategory.traffic_surge:       0.10,
    RcaCategory.error_propagation:   0.10,
    RcaCategory.slo_burn:            0.03,
    RcaCategory.unknown:             0.02,
}

_LIKELIHOODS: Dict[RcaCategory, Dict[str, float]] = {
    RcaCategory.deployment: {
        "has_deployment_event": 0.95,
        "has_metric_spike":     0.70,
        "has_log_burst":        0.60,
        "has_latency_spike":    0.50,
        "has_error_propagation":0.40,
    },
    RcaCategory.resource_exhaustion: {
        "has_deployment_event": 0.15,
        "has_metric_spike":     0.90,
        "has_log_burst":        0.50,
        "has_latency_spike":    0.70,
        "has_error_propagation":0.30,
    },
    RcaCategory.dependency_failure: {
        "has_deployment_event": 0.10,
        "has_metric_spike":     0.50,
        "has_log_burst":        0.70,
        "has_latency_spike":    0.95,
        "has_error_propagation":0.80,
    },
    RcaCategory.traffic_surge: {
        "has_deployment_event": 0.05,
        "has_metric_spike":     0.95,
        "has_log_burst":        0.60,
        "has_latency_spike":    0.60,
        "has_error_propagation":0.20,
    },
    RcaCategory.error_propagation: {
        "has_deployment_event": 0.10,
        "has_metric_spike":     0.60,
        "has_log_burst":        0.80,
        "has_latency_spike":    0.85,
        "has_error_propagation":0.99,
    },
    RcaCategory.slo_burn: {
        "has_deployment_event": 0.20,
        "has_metric_spike":     0.80,
        "has_log_burst":        0.50,
        "has_latency_spike":    0.60,
        "has_error_propagation":0.50,
    },
    RcaCategory.unknown: {
        "has_deployment_event": 0.05,
        "has_metric_spike":     0.30,
        "has_log_burst":        0.30,
        "has_latency_spike":    0.30,
        "has_error_propagation":0.10,
    },
}


@dataclass(frozen=True)
class BayesianScore:
    category: RcaCategory
    posterior: float
    prior: float
    likelihood: float


def score(
    has_deployment_event: bool,
    has_metric_spike: bool,
    has_log_burst: bool,
    has_latency_spike: bool,
    has_error_propagation: bool,
) -> List[BayesianScore]:
    evidence: Dict[str, bool] = {
        "has_deployment_event": has_deployment_event,
        "has_metric_spike":     has_metric_spike,
        "has_log_burst":        has_log_burst,
        "has_latency_spike":    has_latency_spike,
        "has_error_propagation":has_error_propagation,
    }

    raw_posteriors: Dict[RcaCategory, float] = {}
    for category, prior in _PRIORS.items():
        likelihood = 1.0
        likelihoods = _LIKELIHOODS.get(category, {})
        for feature, present in evidence.items():
            p = likelihoods.get(feature, 0.5)
            likelihood *= p if present else (1.0 - p)
        raw_posteriors[category] = prior * likelihood

    total = sum(raw_posteriors.values()) or 1.0
    results = [
        BayesianScore(
            category=cat,
            posterior=round(raw / total, 4),
            prior=round(_PRIORS[cat], 4),
            likelihood=round(raw / _PRIORS[cat] if _PRIORS[cat] else 0.0, 4),
        )
        for cat, raw in raw_posteriors.items()
    ]
    return sorted(results, key=lambda s: s.posterior, reverse=True)