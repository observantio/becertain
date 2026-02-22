from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from engine.enums import Signal
from engine.registry import get_registry

router = APIRouter(tags=["ML"])


@router.post("/ml/weights/feedback", summary="Submit signal correctness feedback")
async def signal_feedback(tenant_id: str, signal: str, was_correct: bool) -> Dict[str, Any]:
    try:
        sig = Signal(signal)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown signal '{signal}'. Valid values: {[s.value for s in Signal]}",
        )
    try:
        state = await get_registry().update_weight(tenant_id, sig, was_correct)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"updated_weights": state.weights, "update_count": state.update_count}


@router.get("/ml/weights", summary="Current adaptive signal weights for a tenant")
async def get_signal_weights(tenant_id: str) -> Dict[str, Any]:
    try:
        state = await get_registry().get_state(tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"weights": state.weights, "update_count": state.update_count}


@router.post("/ml/weights/reset", summary="Reset adaptive weights to defaults for a tenant")
async def reset_signal_weights(tenant_id: str) -> Dict[str, Any]:
    try:
        state = await get_registry().reset_weights(tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"weights": state.weights, "update_count": state.update_count}