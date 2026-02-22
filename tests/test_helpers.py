import asyncio
import pytest
import httpx

from datasources.helpers import fetch_json, fetch_text
from datasources.exceptions import InvalidQuery, QueryTimeout, DataSourceUnavailable


class DummyResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)

    def json(self):
        return self._json


class DummyClient:
    def __init__(self, resp: DummyResponse):
        self.resp = resp

    async def __aenter__(self):
        return self
n
    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None, headers=None):
        return self.resp


@pytest.mark.asyncio
async def test_fetch_json_success(monkeypatch):
    resp = DummyResponse(status_code=200, json_data={"foo": "bar"})
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: DummyClient(resp))
    got = await fetch_json("url", params={"a": 1}, headers={})
    assert got == {"foo": "bar"}

@pytest.mark.asyncio
async def test_fetch_json_http_error(monkeypatch):
    resp = DummyResponse(status_code=404, text="not found")
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: DummyClient(resp))
    with pytest.raises(InvalidQuery):
        await fetch_json("url")

@pytest.mark.asyncio
async def test_fetch_json_timeout(monkeypatch):
    async def get(*args, **kwargs):
        raise httpx.TimeoutException()
    client = DummyClient(DummyResponse())
    client.get = get
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client)
    with pytest.raises(QueryTimeout):
        await fetch_json("url")

@pytest.mark.asyncio
async def test_fetch_text_success(monkeypatch):
    resp = DummyResponse(status_code=200, text="hello")
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: DummyClient(resp))
    got = await fetch_text("url")
    assert got == "hello"
