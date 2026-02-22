from __future__ import annotations

import json
import logging
from typing import Any, Optional, Dict

from store.client import redis_get, redis_set, redis_delete
from config import WEIGHTS_TTL
from store import keys

log = logging.getLogger(__name__)


def weights(tenant_id: str) -> str:
    """Redis key for adaptive signal weights of a tenant."""
    return keys.weights(tenant_id)


async def load(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Load saved weights state for *tenant_id*.

    Returns ``{"weights": {...}, "update_count": n}`` or ``None``.
    """
    try:
        raw = await redis_get(weights(tenant_id))
        if raw:
            return json.loads(raw)
    except Exception as exc:
        log.debug("Weights load failed %s: %s", tenant_id, exc)
    return None


async def save(tenant_id: str, weight_map: Dict[str, float], update_count: int) -> None:
    """Persist the state with a TTL."""
    payload = {"weights": weight_map, "update_count": update_count}
    try:
        # call the helper function to compute the redis key
        await redis_set(weights(tenant_id), json.dumps(payload), ttl=WEIGHTS_TTL)
    except Exception as exc:
        log.debug("Weights save failed %s: %s", tenant_id, exc)


async def delete(tenant_id: str) -> None:
    """Remove any stored state for *tenant_id*."""
    try:
        await redis_delete(weights(tenant_id))
    except Exception as exc:
        log.debug("Weights delete failed %s: %s", tenant_id, exc)
