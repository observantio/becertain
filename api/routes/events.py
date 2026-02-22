"""
Event registration routes for recording deployment events and other relevant occurrences that can be used for RCA correlation.

Copyright (c) 2026 Stefan Kumarasinghe
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from engine.events.registry import DeploymentEvent
from api.routes.exception import handle_exceptions
from api.routes.common import get_provider
from engine.registry import get_registry
from api.requests import DeploymentEventRequest

router = APIRouter(tags=["Events"])


@router.post("/events/deployment", summary="Register a deployment event for RCA correlation")
@handle_exceptions
async def register_deployment(req: DeploymentEventRequest, tenant_id: str | None = None) -> Dict[str, str]:
    tid = tenant_id or get_provider(req.tenant_id)

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
    return {"status": "registered", "service": req.service, "version": req.version}


@router.get("/events/deployments", summary="List registered deployment events for a tenant")
@handle_exceptions
async def list_deployments(tenant_id: str) -> List[Dict[str, Any]]:
    return await get_registry().get_events(tenant_id)


@router.delete("/events/deployments", summary="Clear all deployment events for a tenant")
@handle_exceptions
async def clear_deployments(tenant_id: str) -> Dict[str, str]:
    await get_registry().clear_events(tenant_id)
    return {"status": "cleared", "tenant_id": tenant_id}