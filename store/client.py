"""
Client code for Redis access, with in-memory fallback if Redis is unavailable.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

_redis_client: Any = None
_fallback: dict[str, str] = {}
_fallback_lists: dict[str, list[str]] = {}
_using_fallback = False
_init_lock = asyncio.Lock()
_MAX_FALLBACK_SIZE = 10_000


async def get_redis() -> Any:
    global _redis_client, _using_fallback

    if _redis_client is not None:
        return _redis_client

    async with _init_lock:
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
        if len(_fallback) < _MAX_FALLBACK_SIZE:
            _fallback[key] = value
        return
    try:
        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)
    except Exception as exc:
        log.debug("Redis SET error %s: %s", key, exc)
        if len(_fallback) < _MAX_FALLBACK_SIZE:
            _fallback[key] = value


async def redis_delete(key: str) -> None:
    client = await get_redis()
    if client is None:
        _fallback.pop(key, None)
        _fallback_lists.pop(key, None)
        return
    try:
        await client.delete(key)
    except Exception as exc:
        log.debug("Redis DEL error %s: %s", key, exc)
        _fallback.pop(key, None)
        _fallback_lists.pop(key, None)


async def redis_rpush(key: str, value: str, ttl: Optional[int] = None, max_len: Optional[int] = None) -> None:
    client = await get_redis()
    if client is None:
        lst = _fallback_lists.setdefault(key, [])
        lst.append(value)
        if max_len and len(lst) > max_len:
            del lst[:-max_len]
        return
    try:
        pipe = client.pipeline()
        pipe.rpush(key, value)
        if max_len:
            pipe.ltrim(key, -max_len, -1)
        if ttl:
            pipe.expire(key, ttl)
        await pipe.execute()
    except Exception as exc:
        log.debug("Redis RPUSH error %s: %s", key, exc)
        lst = _fallback_lists.setdefault(key, [])
        lst.append(value)
        if max_len and len(lst) > max_len:
            del lst[:-max_len]


async def redis_lrange(key: str) -> list[str]:
    client = await get_redis()
    if client is None:
        return list(_fallback_lists.get(key, []))
    try:
        return await client.lrange(key, 0, -1)
    except Exception as exc:
        log.debug("Redis LRANGE error %s: %s", key, exc)
        return list(_fallback_lists.get(key, []))


async def redis_scan(pattern: str) -> list[str]:
    client = await get_redis()
    if client is None:
        return [k for k in _fallback if fnmatch.fnmatch(k, pattern)]
    try:
        return [key async for key in client.scan_iter(pattern)]
    except Exception as exc:
        log.debug("Redis SCAN error %s: %s", pattern, exc)
        return [k for k in _fallback if fnmatch.fnmatch(k, pattern)]


def is_using_fallback() -> bool:
    return _using_fallback