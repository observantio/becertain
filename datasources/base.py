"""
Base connectors and shared utilities for data sources

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseConnector(ABC):
    health_path: str = ""

    def __init__(self, tenant_id: str, base_url: str, timeout: int = 30, headers: Optional[Dict[str, str]] = None):
        self.tenant_id = tenant_id
        self.base_url = str(base_url).rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}

    @property
    def health_url(self) -> str:
        if not self.health_path:
            raise NotImplementedError("connector must define health_path")
        return f"{self.base_url}{self.health_path}"

    def _headers(self) -> Dict[str, str]:
        """Basic header set applied to every outbound request."""
        return {**self.headers, "X-Scope-OrgID": self.tenant_id}


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