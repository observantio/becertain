"""
Tests for metric/changepoint route semantics.
"""

from __future__ import annotations

import pytest

from api.requests import ChangepointRequest
from api.routes import metrics as metrics_route


class DummyProvider:
    async def query_metrics(self, query, start, end, step):
        return {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"__name__": "m"},
                        "values": [[1, "1"], [2, "1"], [3, "2"], [4, "2"]],
                    }
                ]
            },
        }


@pytest.mark.asyncio
async def test_changepoints_route_uses_threshold_sigma_explicitly(monkeypatch):
    provider = DummyProvider()
    captured = {"threshold_sigma": None}

    def fake_detect(ts, vals, threshold_sigma=None, metric_name="metric"):
        captured["threshold_sigma"] = threshold_sigma
        return []

    monkeypatch.setattr(metrics_route, "get_provider", lambda tenant_id: provider)
    monkeypatch.setattr(metrics_route, "changepoint_detect", fake_detect)

    req = ChangepointRequest(
        tenant_id="t1",
        query="up",
        start=1,
        end=5,
        step="15s",
        threshold_sigma=7.0,
    )
    rows = await metrics_route.metric_changepoints(req)

    assert rows == []
    assert captured["threshold_sigma"] == 7.0
