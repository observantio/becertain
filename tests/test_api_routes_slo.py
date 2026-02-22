import pytest

from api.routes import slo as slo_route
from api.requests import SloRequest
from config import settings


class DummyProvider:
    def __init__(self):
        self.queries = []

    async def query_metrics(self, query, start, end, step):
        # record query and return minimal valid response
        self.queries.append(query)
        return {"data": {"result": [{"metric": {}, "values": [[1, "0"]]}]}}


async def dummy_slo_evaluate(service, err_vals, tot_vals, ts, target):
    return []


async def dummy_remaining(service, err_vals, tot_vals, target):
    return None


@pytest.mark.asyncio
async def test_slo_burn_default_queries(monkeypatch):
    dummy = DummyProvider()
    monkeypatch.setattr(slo_route, "get_provider", lambda tid: dummy)
    monkeypatch.setattr(slo_route, "slo_evaluate", dummy_slo_evaluate)
    monkeypatch.setattr(slo_route, "remaining_minutes", dummy_remaining)

    req = SloRequest(service="abc", start=0, end=1, step=1, target_availability=0.99)
    await slo_route.slo_burn(req)

    assert dummy.queries[0] == settings.slo_error_query_template.format(service="abc")
    assert dummy.queries[1] == settings.slo_total_query_template.format(service="abc")


@pytest.mark.asyncio
async def test_slo_burn_custom_queries_override(monkeypatch):
    dummy = DummyProvider()
    monkeypatch.setattr(slo_route, "get_provider", lambda tid: dummy)
    monkeypatch.setattr(slo_route, "slo_evaluate", dummy_slo_evaluate)
    monkeypatch.setattr(slo_route, "remaining_minutes", dummy_remaining)

    req = SloRequest(
        service="abc",
        start=0,
        end=1,
        step=1,
        target_availability=0.99,
        error_query="errQ",
        total_query="totQ",
    )
    await slo_route.slo_burn(req)

    assert dummy.queries == ["errQ", "totQ"]
