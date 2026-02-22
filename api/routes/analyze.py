from __future__ import annotations

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine.analyzer import run
from api.requests import AnalyzeRequest
from api.responses import AnalysisReport

router = APIRouter(tags=["RCA"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


@router.post("/analyze", response_model=AnalysisReport, summary="Full cross-signal RCA")
async def analyze(req: AnalyzeRequest) -> AnalysisReport:
    try:
        return await run(_provider(req.tenant_id), req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc