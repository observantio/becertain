# datasource/provider.py

from typing import Dict, Any, Optional
from .data_config import DataSourceSettings
from .factory import DataSourceFactory
from .exceptions import DataSourceError

class DataSourceProvider:
    """
    Unified provider for logs, metrics, and traces.
    Wraps vendor connectors and enforces tenant isolation.
    """

    def __init__(self, tenant_id: str, settings: DataSourceSettings):
        self.tenant_id = tenant_id
        self.settings = settings
        self.logs = DataSourceFactory.create_logs(settings, tenant_id)
        self.metrics = DataSourceFactory.create_metrics(settings, tenant_id)
        self.traces = DataSourceFactory.create_traces(settings, tenant_id)

    async def query_logs(self, query: str, start: int, end: int, limit: Optional[int] = None) -> Dict[str, Any]:
        try:
            return await self.logs.query_range(query=query, start=start, end=end, limit=limit)
        except DataSourceError as e:
            raise 
            
    async def query_metrics(self, query: str, start: int, end: int, step: str) -> Dict[str, Any]:
        try:
            return await self.metrics.query_range(query=query, start=start, end=end, step=step)
        except DataSourceError as e:
            raise

    async def query_traces(self, filters: Dict[str, Any], start: int, end: int, limit: Optional[int] = None) -> Dict[str, Any]:
        try:
            return await self.traces.query_range(filters=filters, start=start, end=end, limit=limit)
        except DataSourceError as e:
            raise