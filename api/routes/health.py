from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from store.client import get_redis, is_using_fallback

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> Dict[str, Any]:
    await get_redis()
    return {
        "status": "ok",
        "store": "fallback" if is_using_fallback() else "redis",
    }