from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine import anomaly
from engine.baseline import compute as baseline_compute
from engine.changepoint import detect as changepoint_detect, ChangePoint
from api.requests import MetricRequest, ChangepointRequest
from api.responses import MetricAnomaly

router = APIRouter(tags=["Metrics"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


@router.post("/anomalies/metrics", response_model=List[MetricAnomaly])
async def metric_anomalies(req: MetricRequest) -> List[MetricAnomaly]:
    try:
        raw = await _provider(req.tenant_id).query_metrics(
            query=req.query, start=req.start, end=req.end, step=req.step
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results = []
    for metric, ts, vals in anomaly.iter_series(raw):
        results.extend(anomaly.detect(metric, ts, vals, req.sensitivity))
    return sorted(results, key=lambda a: a.timestamp)


@router.post("/changepoints", response_model=List[ChangePoint])
async def metric_changepoints(req: ChangepointRequest) -> List[ChangePoint]:
    try:
        raw = await _provider(req.tenant_id).query_metrics(
            query=req.query, start=req.start, end=req.end, step=req.step
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results: List[ChangePoint] = []
    for _, ts, vals in anomaly.iter_series(raw):
        baseline = baseline_compute(ts, vals)
        results.extend(changepoint_detect(ts, vals, threshold_sigma=req.threshold_sigma or baseline.std))
    return sorted(results, key=lambda c: c.timestamp)