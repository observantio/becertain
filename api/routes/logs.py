from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine import logs
from api.requests import LogRequest
from api.responses import LogBurst, LogPattern

router = APIRouter(tags=["Logs"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


def _ns(ts: int) -> int:
    return ts * 1_000_000_000


@router.post("/anomalies/logs/patterns", response_model=List[LogPattern])
async def log_patterns(req: LogRequest) -> List[LogPattern]:
    try:
        raw = await _provider(req.tenant_id).query_logs(
            query=req.query, start=_ns(req.start), end=_ns(req.end)
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return logs.analyze(raw)


@router.post("/anomalies/logs/bursts", response_model=List[LogBurst])
async def log_bursts(req: LogRequest) -> List[LogBurst]:
    try:
        raw = await _provider(req.tenant_id).query_logs(
            query=req.query, start=_ns(req.start), end=_ns(req.end)
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return logs.detect_bursts(raw)