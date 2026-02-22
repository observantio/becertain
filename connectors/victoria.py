"""
VictoriaMetrics Connector

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""
import httpx
from typing import Any, Dict, Optional

from datasources.retry import retry

from datasources.base import MetricsConnector
from datasources.helpers import fetch_json
from datasources.exceptions import DataSourceUnavailable, InvalidQuery, QueryTimeout
from config import HEALTH_PATH, DATASOURCE_TIMEOUT

class VictoriaMetricsConnector(MetricsConnector):
    # health_path used by the shared property in BaseConnector
    health_path = HEALTH_PATH

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        timeout: int = DATASOURCE_TIMEOUT,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(tenant_id, base_url, timeout, headers)

    @retry(attempts=3, delay=0.5, backoff=2.0, exceptions=(httpx.RequestError, httpx.TimeoutException))
    async def query_range(
        self,
        query: str,
        start: int,
        end: int,
        step: str,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/query_range"
        params: Dict[str, Any] = {"query": query, "start": start, "end": end, "step": step}
        return await fetch_json(
            url,
            params=params,
            headers=self._headers(),
            timeout=self.timeout,
            invalid_msg="VictoriaMetrics query failed",
            timeout_msg="VictoriaMetrics query timed out",
            unavailable_msg="Cannot reach VictoriaMetrics at",
        )