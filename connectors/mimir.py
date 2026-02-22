# datasource/connectors/mimir.py

import httpx
from typing import Any, Dict, Optional

from datasources.base import MetricsConnector
from datasources.exceptions import DataSourceUnavailable, InvalidQuery, QueryTimeout

HEALTH_PATH = "/ready"


class MimirConnector(MetricsConnector):
    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(tenant_id)
        self.base_url = str(base_url).rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}

    @property
    def health_url(self) -> str:
        return f"{self.base_url}{HEALTH_PATH}"

    def _headers(self) -> Dict[str, str]:
        return {**self.headers, "X-Scope-OrgID": self.tenant_id}

    async def scrape(self) -> str:
        """Fetch the plain Prometheus metrics exposition text for this tenant."""
        url = f"{self.base_url}/metrics"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self._headers())
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            raise

    async def query_range(
        self,
        query: str,
        start: int,
        end: int,
        step: str,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/prometheus/api/v1/query_range"
        params: Dict[str, Any] = {"query": query, "start": start, "end": end, "step": step}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            raise InvalidQuery(f"Mimir query failed [{e.response.status_code}]: {e.response.text}") from e
        except httpx.TimeoutException as e:
            raise QueryTimeout("Mimir query timed out") from e
        except httpx.RequestError as e:
            raise DataSourceUnavailable(f"Cannot reach Mimir at {url}") from e