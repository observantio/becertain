"""
Metric analysis routes for detecting anomalies and changepoints in time series data.

Copyright (c) 2026 Stefan Kumarasinghe
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter

from api.routes.common import get_provider, safe_call
from api.routes.exception import handle_exceptions
from services.security_service import enforce_request_tenant
from engine import anomaly
from engine.baseline import compute as baseline_compute
from engine.changepoint import detect as changepoint_detect, ChangePoint
from api.requests import MetricRequest, ChangepointRequest
from api.responses import MetricAnomaly

router = APIRouter(tags=["Metrics"])

# provider helper moved to api.routes.common


@router.post("/anomalies/metrics", response_model=List[MetricAnomaly])
@handle_exceptions
async def metric_anomalies(req: MetricRequest) -> List[MetricAnomaly]:
    req = enforce_request_tenant(req)
    raw = await safe_call(
        get_provider(req.tenant_id).query_metrics(
            query=req.query, start=req.start, end=req.end, step=req.step
        )
    )

    results = []
    for metric, ts, vals in anomaly.iter_series(raw, query_hint=req.query):
        results.extend(anomaly.detect(metric, ts, vals, req.sensitivity))
    return sorted(results, key=lambda a: a.timestamp)


@router.post("/changepoints", response_model=List[ChangePoint])
@handle_exceptions
async def metric_changepoints(req: ChangepointRequest) -> List[ChangePoint]:
    req = enforce_request_tenant(req)
    raw = await safe_call(
        get_provider(req.tenant_id).query_metrics(
            query=req.query, start=req.start, end=req.end, step=req.step
        )
    )

    results: List[ChangePoint] = []
    for metric_name, ts, vals in anomaly.iter_series(raw, query_hint=req.query):
        baseline = baseline_compute(ts, vals)
        results.extend(
            changepoint_detect(
                ts,
                vals,
                threshold_sigma=req.threshold_sigma or baseline.std,
                metric_name=metric_name,
            )
        )
    return sorted(results, key=lambda c: c.timestamp)
