"""
Tests for trace anomaly route behavior.
"""

from __future__ import annotations

import pytest

from api.requests import TraceRequest
from api.routes import traces as traces_route


class DummyProvider:
    def __init__(self) -> None:
        self.filters = None

    async def query_traces(self, filters, start, end, limit=None):
        self.filters = dict(filters)
        return {"traces": []}


@pytest.mark.asyncio
async def test_trace_route_does_not_force_default_service_filter(monkeypatch):
    provider = DummyProvider()
    monkeypatch.setattr(traces_route, "get_provider", lambda tid: provider)
    monkeypatch.setattr(traces_route.traces, "analyze", lambda raw, apdex: [])

    req = TraceRequest(tenant_id="t1", start=1, end=2)
    rows = await traces_route.trace_anomalies(req)

    assert rows == []
    assert provider.filters == {}
