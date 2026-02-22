from __future__ import annotations

import json
import logging
from typing import List

from store.client import redis_get, redis_set, redis_delete
from config import EVENTS_TTL
from store import keys

log = logging.getLogger(__name__)


def _serialise(event) -> dict:
    return {
        "service": event.service,
        "timestamp": event.timestamp,
        "version": event.version,
        "author": event.author,
        "environment": event.environment,
        "source": event.source,
        "metadata": dict(event.metadata),
    }


async def load(tenant_id: str) -> List[dict]:
    try:
        raw = await redis_get(keys.events(tenant_id))
        if raw:
            return json.loads(raw)
    except Exception as exc:
        log.debug("Events load failed %s: %s", tenant_id, exc)
    return []


async def append(tenant_id: str, event) -> None:
    existing = await load(tenant_id)
    existing.append(_serialise(event))
    try:
        await redis_set(keys.events(tenant_id), json.dumps(existing), ttl=EVENTS_TTL)
    except Exception as exc:
        log.debug("Events append failed %s: %s", tenant_id, exc)


async def clear(tenant_id: str) -> None:
    try:
        await redis_delete(keys.events(tenant_id))
    except Exception as exc:
        log.debug("Events clear failed %s: %s", tenant_id, exc)