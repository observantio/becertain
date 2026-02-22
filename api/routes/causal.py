"""
Causal inference routes for root cause analysis.

Copyright (c) 2026 Stefan Kumarasinghe
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from api.routes.common import get_provider, safe_call
from api.routes.exception import handle_exceptions
from engine import anomaly
from engine.causal import CausalGraph, bayesian_score, test_all_pairs
from engine.constants import DEFAULT_METRIC_QUERIES
from engine.fetcher import fetch_metrics
from engine.registry import get_registry
from store import granger as granger_store
from api.requests import CorrelateRequest, AnalyzeRequest
from config import DEFAULT_SERVICE_NAME

router = APIRouter(tags=["Causal"])



@router.post("/causal/granger", summary="Granger causality between metrics (warm model via Redis)")
@handle_exceptions
async def granger_causality(req: CorrelateRequest) -> Dict[str, Any]:
    provider = get_provider(req.tenant_id)
    all_queries = list(dict.fromkeys((req.metric_queries or []) + DEFAULT_METRIC_QUERIES))

    metrics_raw = await safe_call(
        fetch_metrics(provider, all_queries, req.start, req.end, req.step)
    )

    series_map: Dict[str, list] = {}
    for resp in metrics_raw:
        for metric_name, _, vals in anomaly.iter_series(resp):
            series_map[metric_name] = vals

    fresh_results = test_all_pairs(series_map)
    service_label = req.services[0] if req.services else DEFAULT_SERVICE_NAME
    merged = await granger_store.save_and_merge(req.tenant_id, service_label, fresh_results)

    causal_graph = CausalGraph()
    causal_graph.from_granger_results(fresh_results)

    return {
        "fresh_pairs": len(fresh_results),
        "warm_model_pairs": len(merged),
        "causal_pairs": [r.__dict__ for r in fresh_results],
        "warm_causal_pairs": merged,
        "root_causes": causal_graph.root_causes(),
        "interventions": {
            root: causal_graph.simulate_intervention(root).__dict__
            for root in causal_graph.root_causes()
        },
        "topological_order": causal_graph.topological_sort(),
    }


@router.post("/causal/bayesian", summary="Bayesian posterior over RCA categories given observed signals")
@handle_exceptions
async def bayesian_rca(req: AnalyzeRequest) -> Dict[str, Any]:
    deployment_events = await get_registry().events_in_window(req.tenant_id, req.start, req.end)
    scores = bayesian_score(
        has_deployment_event=bool(deployment_events),
        has_metric_spike=bool(req.metric_queries),
        has_log_burst=bool(req.log_query),
        has_latency_spike=bool(req.services),
        has_error_propagation=False,
    )
    return {
        "posteriors": [
            {"category": s.category.value, "posterior": s.posterior, "prior": s.prior}
            for s in scores
        ]
    }