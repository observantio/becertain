from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider
from engine import anomaly, logs
from engine.constants import DEFAULT_METRIC_QUERIES
from engine.correlation import correlate, link_logs_to_metrics
from engine.fetcher import fetch_metrics
from api.requests import CorrelateRequest

router = APIRouter(tags=["Correlation"])


def _provider(tenant_id: str) -> DataSourceProvider:
    return DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())


@router.post("/correlate", summary="Cross-signal temporal correlation without full RCA")
async def correlate_signals(req: CorrelateRequest) -> Dict[str, Any]:
    log_query = req.log_query or (
        '{service=~"' + "|".join(req.services) + '"}' if req.services else '{job=~".+"}'
    )
    provider = _provider(req.tenant_id)
    all_queries = list(dict.fromkeys((req.metric_queries or []) + DEFAULT_METRIC_QUERIES))

    logs_raw, metrics_raw = await asyncio.gather(
        provider.query_logs(
            query=log_query,
            start=req.start * 1_000_000_000,
            end=req.end * 1_000_000_000,
        ),
        fetch_metrics(provider, all_queries, req.start, req.end, req.step),
        return_exceptions=True,
    )

    metric_anomalies = []
    if not isinstance(metrics_raw, Exception):
        for resp in metrics_raw:
            for metric_name, ts, vals in anomaly.iter_series(resp):
                metric_anomalies.extend(anomaly.detect(metric_name, ts, vals))

    log_bursts_list = []
    if not isinstance(logs_raw, Exception):
        log_bursts_list = logs.detect_bursts(logs_raw)

    events = correlate(metric_anomalies, log_bursts_list, [], window_seconds=req.window_seconds)
    links = link_logs_to_metrics(metric_anomalies, log_bursts_list)

    return {
        "correlated_events": [
            {
                "window_start": e.window_start,
                "window_end": e.window_end,
                "confidence": e.confidence,
                "signal_count": e.signal_count,
                "metric_anomaly_count": len(e.metric_anomalies),
                "log_burst_count": len(e.log_bursts),
            }
            for e in events
        ],
        "log_metric_links": [
            {
                "metric_name": lk.metric_name,
                "log_stream": lk.log_stream,
                "lag_seconds": lk.lag_seconds,
                "strength": lk.strength,
            }
            for lk in links
        ],
    }