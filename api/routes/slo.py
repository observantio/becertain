from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine import anomaly
from engine.slo import evaluate as slo_evaluate, remaining_minutes
from api.requests import SloRequest

router = APIRouter(tags=["SLO"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


@router.post("/slo/burn", summary="SLO error budget burn rate")
async def slo_burn(req: SloRequest) -> Dict[str, Any]:
    error_q = req.error_query or (
        f'sum(rate(http_requests_total{{service="{req.service}",status=~"5.."}}[5m]))'
    )
    total_q = req.total_query or (
        f'sum(rate(http_requests_total{{service="{req.service}"}}[5m]))'
    )
    provider = _provider(req.tenant_id)

    err_raw, tot_raw = await asyncio.gather(
        provider.query_metrics(query=error_q, start=req.start, end=req.end, step=req.step),
        provider.query_metrics(query=total_q, start=req.start, end=req.end, step=req.step),
        return_exceptions=True,
    )

    if isinstance(err_raw, Exception):
        raise HTTPException(status_code=502, detail=str(err_raw))
    if isinstance(tot_raw, Exception):
        raise HTTPException(status_code=502, detail=str(tot_raw))

    err_series = list(anomaly.iter_series(err_raw))
    tot_series = list(anomaly.iter_series(tot_raw))

    alerts = []
    budget = None
    for (_, err_ts, err_vals), (_, _tot_ts, tot_vals) in zip(err_series, tot_series):
        alerts.extend(slo_evaluate(req.service, err_vals, tot_vals, err_ts, req.target_availability))
        budget = remaining_minutes(req.service, err_vals, tot_vals, req.target_availability)

    return {
        "burn_alerts": [a.__dict__ for a in alerts],
        "budget_status": budget.__dict__ if budget else None,
    }