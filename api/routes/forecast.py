from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine import anomaly
from engine.constants import DEFAULT_METRIC_QUERIES, FORECAST_THRESHOLDS
from engine.fetcher import fetch_metrics
from engine.forecast import analyze_degradation, forecast
from api.requests import CorrelateRequest

router = APIRouter(tags=["Forecast"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


@router.post("/forecast/trajectory", summary="Time-to-failure and degradation trajectory per metric")
async def metric_trajectory(req: CorrelateRequest) -> Dict[str, Any]:
    provider = _provider(req.tenant_id)
    all_queries = list(dict.fromkeys((req.metric_queries or []) + DEFAULT_METRIC_QUERIES))

    try:
        metrics_raw = await fetch_metrics(provider, all_queries, req.start, req.end, req.step)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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