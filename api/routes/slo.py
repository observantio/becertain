"""
SLO routes for detecting metric anomalies and changepoints based on user-defined sensitivity and thresholds.

Copyright (c) 2026 Stefan Kumarasinghe
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter

from api.routes.common import get_provider, safe_call
from api.routes.exception import handle_exceptions
from engine import anomaly
from engine.slo import evaluate as slo_evaluate, remaining_minutes
from api.requests import SloRequest
from config import settings

router = APIRouter(tags=["SLO"])



@router.post("/slo/burn", summary="SLO error budget burn rate")
@handle_exceptions
async def slo_burn(req: SloRequest) -> Dict[str, Any]:
    error_q = req.error_query or settings.slo_error_query_template.format(service=req.service)
    total_q = req.total_query or settings.slo_total_query_template.format(service=req.service)
    provider = get_provider(req.tenant_id)

    err_raw = await safe_call(
        provider.query_metrics(query=error_q, start=req.start, end=req.end, step=req.step)
    )
    tot_raw = await safe_call(
        provider.query_metrics(query=total_q, start=req.start, end=req.end, step=req.step)
    )

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