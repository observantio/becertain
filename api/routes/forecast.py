"""
Forecast routes for quick cross-signal temporal correlation without full RCA.

Copyright (c) 2026 Stefan Kumarasinghe
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from api.routes.common import get_provider, safe_call
from api.routes.exception import handle_exceptions
from engine import anomaly
from config import DEFAULT_METRIC_QUERIES, FORECAST_THRESHOLDS
from engine.fetcher import fetch_metrics
from engine.forecast import analyze_degradation, forecast
from api.requests import CorrelateRequest

router = APIRouter(tags=["Forecast"])



@router.post("/forecast/trajectory", summary="Time-to-failure and degradation trajectory per metric")
@handle_exceptions
async def metric_trajectory(req: CorrelateRequest) -> Dict[str, Any]:
    provider = get_provider(req.tenant_id)
    all_queries = list(dict.fromkeys((req.metric_queries or []) + DEFAULT_METRIC_QUERIES))

    metrics_raw = await safe_call(
        fetch_metrics(provider, all_queries, req.start, req.end, req.step)
    )

    results: List[Dict[str, Any]] = []
    for resp in metrics_raw:
        for metric_name, ts, vals in anomaly.iter_series(resp):
            threshold = next(
                (v for k, v in FORECAST_THRESHOLDS.items() if k in metric_name), None
            )
            f = forecast(metric_name, ts, vals, threshold) if threshold else None
            deg = analyze_degradation(metric_name, ts, vals)
            if f or deg:
                results.append({
                    "metric": metric_name,
                    "forecast": f.__dict__ if f else None,
                    "degradation": deg.__dict__ if deg else None,
                })

    return {"results": results}