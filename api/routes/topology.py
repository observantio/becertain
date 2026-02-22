from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine.topology import DependencyGraph
from api.requests import TopologyRequest

router = APIRouter(tags=["Topology"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


@router.post("/topology/blast-radius", summary="Service dependency blast radius from traces")
async def blast_radius(req: TopologyRequest) -> Dict[str, Any]:
    try:
        raw = await _provider(req.tenant_id).query_traces(
            filters={}, start=req.start, end=req.end
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    graph = DependencyGraph()
    if isinstance(raw, list):
        graph.from_spans(raw)

    radius = graph.blast_radius(req.root_service, max_depth=req.max_depth)
    upstream = graph.find_upstream_roots(req.root_service)

    return {
        "root_service": radius.root_service,
        "affected_downstream": radius.affected_downstream,
        "upstream_roots": upstream,
        "all_services": sorted(graph.all_services()),
    }