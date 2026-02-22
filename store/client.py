from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

_redis_client: Any = None
_fallback: dict[str, str] = {}
_using_fallback = False


async def get_redis() -> Any:
    global _redis_client, _using_fallback

    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as aioredis
        from config import REDIS_URL

        client = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await client.ping()
        _redis_client = client
        _using_fallback = False
        log.info("Redis connected: %s", REDIS_URL)
        return _redis_client
    except Exception as exc:
        if not _using_fallback:
            log.warning("Redis unavailable (%s) — using in-memory fallback", exc)
            _using_fallback = True
        return None


async def redis_get(key: str) -> Optional[str]:
    client = await get_redis()
    if client is None:
        return _fallback.get(key)
    try:
        return await client.get(key)
    except Exception as exc:
        log.debug("Redis GET error %s: %s", key, exc)
        return _fallback.get(key)


async def redis_set(key: str, value: str, ttl: Optional[int] = None) -> None:
    client = await get_redis()
    if client is None:
        _fallback[key] = value
        return
    try:
        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)
    except Exception as exc:
        log.debug("Redis SET error %s: %s", key, exc)
        _fallback[key] = value


async def redis_delete(key: str) -> None:
    client = await get_redis()
    if client is None:
        _fallback.pop(key, None)
        return
    try:
        await client.delete(key)
    except Exception as exc:
        log.debug("Redis DEL error %s: %s", key, exc)
        _fallback.pop(key, None)


async def redis_keys(pattern: str) -> list[str]:
    client = await get_redis()
    if client is None:
        return [k for k in _fallback if _match(k, pattern)]
    try:
        return await client.keys(pattern)
    except Exception as exc:
        log.debug("Redis KEYS error %s: %s", pattern, exc)
        return [k for k in _fallback if _match(k, pattern)]


def _match(key: str, pattern: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(key, pattern)


def is_using_fallback() -> bool:
    return _using_fallback