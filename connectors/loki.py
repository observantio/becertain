import httpx
from typing import Any, Dict, Optional

from datasources.base import LogsConnector
from datasources.exceptions import DataSourceUnavailable, InvalidQuery, QueryTimeout

HEALTH_PATH = "/ready"


class LokiConnector(LogsConnector):
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

    async def query_range(
        self,
        query: str,
        start: int,
        end: int,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/loki/api/v1/query_range"
        params: Dict[str, Any] = {"query": query, "start": start, "end": end}
        if limit is not None:
            params["limit"] = limit

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            raise InvalidQuery(f"Loki query failed [{e.response.status_code}]: {e.response.text}") from e
        except httpx.TimeoutException as e:
            raise QueryTimeout("Loki query timed out") from e
        except httpx.RequestError as e:
            raise DataSourceUnavailable(f"Cannot reach Loki at {url}") from e