"""
Weights storage and retrieval logic.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from store.client import redis_get, redis_set, redis_delete
from config import WEIGHTS_TTL
from store import keys

log = logging.getLogger(__name__)


async def load(tenant_id: str) -> Optional[Dict[str, Any]]:
    try:
        raw = await redis_get(keys.weights(tenant_id))
        if raw:
            return json.loads(raw)
    except Exception as exc:
        log.debug("Weights load failed %s: %s", tenant_id, exc)
    return None


async def save(tenant_id: str, weight_map: Dict[str, float], update_count: int) -> None:
    payload = {"weights": weight_map, "update_count": update_count}
    try:
        await redis_set(keys.weights(tenant_id), json.dumps(payload), ttl=WEIGHTS_TTL)
    except Exception as exc:
        log.debug("Weights save failed %s: %s", tenant_id, exc)


async def delete(tenant_id: str) -> None:
    try:
        await redis_delete(keys.weights(tenant_id))
    except Exception as exc:
        log.debug("Weights delete failed %s: %s", tenant_id, exc)