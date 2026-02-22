import os
import sys
import pytest

# ensure workspace root is on sys.path so our application packages can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from store.client import _fallback, _redis_client


@pytest.fixture(autouse=True)
def clear_fallback(monkeypatch):
    """Wipe the in-memory redis fallback before and after each test and override
    the redis helpers so they always operate on the in-memory store.
    """
    # ensure a clean slate
    _fallback.clear()
    global _redis_client
    _redis_client = None

    # stub out client calls so tests don't attempt network
    import store.client as client

    async def fake_get(key: str):
        return _fallback.get(key)

    async def fake_set(key: str, value: str, ttl=None):
        _fallback[key] = value

    async def fake_delete(key: str):
        _fallback.pop(key, None)

    monkeypatch.setattr(client, "redis_get", fake_get)
    monkeypatch.setattr(client, "redis_set", fake_set)
    monkeypatch.setattr(client, "redis_delete", fake_delete)

    # also update any modules that imported renames at import-time
    import store.weights as wstore
    import store.baseline as bstore
    import store.granger as gstore
    import store.events as estore
    for mod in (wstore, bstore, gstore, estore):
        for name in ("redis_get", "redis_set", "redis_delete"):
            if hasattr(mod, name):
                monkeypatch.setattr(mod, name, locals()[f"fake_{name.split('_')[1]}"])

    yield

    _fallback.clear()
    _redis_client = None


# Prevent pytest from attempting to collect any modules inside the engine
# package itself.  Those files are imported by tests and contain utility
# functions; some of them previously started with "test_" which confused
# test discovery.  Ignoring engine files keeps collection focused on the
# tests directory.

def pytest_ignore_collect(path, config):
    text = str(path)
    if os.path.sep + 'engine' + os.path.sep in text:
        return True
