from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine import traces
from api.requests import TraceRequest
from api.responses import ServiceLatency

router = APIRouter(tags=["Traces"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


@router.post("/anomalies/traces", response_model=List[ServiceLatency])
async def trace_anomalies(req: TraceRequest) -> List[ServiceLatency]:
    filters: Dict[str, Any] = {}
    if req.service:
        filters["service.name"] = req.service
    try:
        raw = await _provider(req.tenant_id).query_traces(
            filters=filters, start=req.start, end=req.end
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return traces.analyze(raw, req.apdex_threshold_ms)