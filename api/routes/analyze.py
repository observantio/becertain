"""
Analyze route for root cause analysis (RCA) across multiple signals.
This gives a comprehensive analysis report including metric anomalies, log bursts, service latency issues, error propagation, and more.
You may filter or specify time ranges and other parameters in the AnalyzeRequest to focus the analysis.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.common import get_provider
from api.routes.exception import handle_exceptions
from api.security import enforce_request_tenant
from engine.analyzer import run
from api.requests import AnalyzeRequest
from api.responses import AnalysisReport

router = APIRouter(tags=["RCA"])


@router.post("/analyze", response_model=AnalysisReport, summary="Full cross-signal RCA")
@handle_exceptions
async def analyze(req: AnalyzeRequest) -> AnalysisReport:
    req = enforce_request_tenant(req)
    return await run(get_provider(req.tenant_id), req)
