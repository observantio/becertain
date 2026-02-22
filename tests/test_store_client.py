import pytest

from store.client import _fallback, redis_get, redis_set, redis_delete, redis_keys, is_using_fallback


@pytest.mark.asyncio
async def test_fallback_operations():
    _fallback.clear()
    await redis_set("k1", "v1")
    assert await redis_get("k1") == "v1"
    await redis_delete("k1")
    assert await redis_get("k1") is None

@pytest.mark.asyncio
async def test_keys_pattern():
    _fallback.clear()
    await redis_set("abc", "1")
    await redis_set("abx", "2")
    keys = await redis_keys("ab*")
    assert "abc" in keys and "abx" in keys
