from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseConnector(ABC):
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id


class LogsConnector(BaseConnector):
    @abstractmethod
    async def query_range(
        self,
        query: str,
        start: int,
        end: int,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]: ...


class MetricsConnector(BaseConnector):
    @abstractmethod
    async def query_range(
        self,
        query: str,
        start: int,
        end: int,
        step: str,
    ) -> Dict[str, Any]: ...


class TracesConnector(BaseConnector):
    @abstractmethod
    async def query_range(
        self,
        filters: Dict[str, Any],
        start: int,
        end: int,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]: ...