"""
Analyze service implementation that runs the core analysis engine with tenant-aware data providers.

Copyright (c) 2026 Stefan Kumarasinghe
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""
from __future__ import annotations

from api.requests import AnalyzeRequest
from api.responses import AnalysisReport
from api.routes.common import get_provider
from engine.analyzer import run
from services.security_service import enforce_request_tenant


async def run_analysis(req: AnalyzeRequest) -> AnalysisReport:
    tenant_req = enforce_request_tenant(req)
    return await run(get_provider(tenant_req.tenant_id), tenant_req)
