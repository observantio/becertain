import pytest

import asyncio
from engine.fetcher import fetch_metrics


class DummyProvider:
    def __init__(self, results):
        self._results = results

    async def query_metrics(self, query, start, end, step):
        if query == "bad":
            raise ValueError("oops")
        return {"query": query, "start": start}


@pytest.mark.asyncio
async def test_fetch_metrics_filters_exceptions():
    provider = DummyProvider(None)
    queries = ["a", "bad", "c"]
    res = await fetch_metrics(provider, queries, 0, 1, "15s")
    assert isinstance(res, list)
    assert all(isinstance(r, dict) for r in res)
    assert len(res) == 2
    assert res[0]["query"] == "a"
