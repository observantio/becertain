from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from engine.events.registry import DeploymentEvent
from engine.registry import get_registry
from api.requests import DeploymentEventRequest

router = APIRouter(tags=["Events"])


@router.post("/events/deployment", summary="Register a deployment event for RCA correlation")
async def register_deployment(req: DeploymentEventRequest, tenant_id: str | None = None) -> Dict[str, str]:
    tid = tenant_id or getattr(req, "tenant_id", None)
    if not tid:
        raise HTTPException(status_code=400, detail="missing tenant_id")

    try:
        await get_registry().register_event(
            tid,
            DeploymentEvent(
                service=req.service,
                timestamp=req.timestamp,
                version=req.version,
                author=req.author,
                environment=req.environment,
                source=req.source,
                metadata=req.metadata,
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "registered", "service": req.service, "version": req.version}


@router.get("/events/deployments", summary="List registered deployment events for a tenant")
async def list_deployments(tenant_id: str) -> List[Dict[str, Any]]:
    try:
        return await get_registry().get_events(tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/events/deployments", summary="Clear all deployment events for a tenant")
async def clear_deployments(tenant_id: str) -> Dict[str, str]:
    try:
        await get_registry().clear_events(tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "cleared", "tenant_id": tenant_id}