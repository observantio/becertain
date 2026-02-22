from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Dict, List, Tuple

from datasources.provider import DataSourceProvider
from engine import anomaly, logs, rca, traces
from engine.causal import CausalGraph, bayesian_score, test_all_pairs
from engine.changepoint import detect as changepoint_detect, ChangePoint
from engine.constants import DEFAULT_METRIC_QUERIES, FORECAST_THRESHOLDS, SLO_ERROR_QUERY, SLO_TOTAL_QUERY
from engine.correlation import correlate, link_logs_to_metrics
from engine.dedup import group_metric_anomalies
from engine.events.registry import DeploymentEvent, EventRegistry
from engine.fetcher import fetch_metrics
from engine.forecast import analyze_degradation, forecast
from engine.ml import cluster, rank
from engine.registry import get_registry
from engine.slo import evaluate as slo_evaluate
from engine.topology import DependencyGraph
from store import baseline as baseline_store, granger as granger_store
from api.requests import AnalyzeRequest
from api.responses import AnalysisReport, RootCause as RootCauseModel, SloBurnAlert as SloBurnAlertModel
from engine.enums import Severity

log = logging.getLogger(__name__)


def _overall_severity(*groups) -> Severity:
    best = Severity.low
    for group in groups:
        for item in group:
            if item.severity.weight() > best.weight():
                best = item.severity
    return best


def _summary(report: AnalysisReport) -> str:
    parts = []
    if report.metric_anomalies:
        groups = group_metric_anomalies(report.metric_anomalies)
        parts.append(f"{len(groups)} metric anomaly group(s)")
    if report.log_bursts:
        parts.append(f"{len(report.log_bursts)} log burst(s)")
    if report.log_patterns:
        hi = [p for p in report.log_patterns if p.severity.weight() >= 3]
        if hi:
            parts.append(f"{sum(p.count for p in hi)} high/critical log events")
    if report.service_latency:
        parts.append(f"{len(report.service_latency)} service(s) degraded")
    if report.error_propagation:
        parts.append(f"error propagation from {report.error_propagation[0].source_service}")
    if report.slo_alerts:
        parts.append(f"{len(report.slo_alerts)} SLO burn alert(s)")
    if report.change_points:
        parts.append(f"{len(report.change_points)} change point(s)")
    if report.forecasts:
        critical = [f for f in report.forecasts if f.severity.weight() >= 4]
        if critical:
            parts.append(f"{len(critical)} imminent breach(es) predicted")
    if report.degradation_signals:
        parts.append(f"{len(report.degradation_signals)} degrading metric(s)")
    if not parts:
        return "No anomalies detected in the analysis window."
    top = f" Top: {report.root_causes[0].hypothesis[:120]}..." if report.root_causes else ""
    return f"[{report.overall_severity.value.upper()}] {' | '.join(parts)}.{top}"


async def run(provider: DataSourceProvider, req: AnalyzeRequest) -> AnalysisReport:
    registry = get_registry()
    tenant_id = req.tenant_id

    log_query = req.log_query or (
        '{service=~"' + "|".join(req.services) + '"}' if req.services else '{job=~".+"}'
    )
    trace_filters = {"service.name": req.services[0]} if req.services else {}
    all_metric_queries = list(dict.fromkeys((req.metric_queries or []) + DEFAULT_METRIC_QUERIES))

    (
        logs_raw,
        traces_raw,
        metrics_raw,
        slo_errors_raw,
        slo_total_raw,
    ) = await asyncio.gather(
        provider.query_logs(
            query=log_query,
            start=req.start * 1_000_000_000,
            end=req.end * 1_000_000_000,
        ),
        provider.query_traces(filters=trace_filters, start=req.start, end=req.end),
        fetch_metrics(provider, all_metric_queries, req.start, req.end, req.step),
        provider.query_metrics(query=SLO_ERROR_QUERY, start=req.start, end=req.end, step=req.step),
        provider.query_metrics(query=SLO_TOTAL_QUERY, start=req.start, end=req.end, step=req.step),
        return_exceptions=True,
    )

    metric_anomalies = []
    change_points: List[ChangePoint] = []
    forecasts = []
    degradation_signals = []
    series_map: Dict[str, List[float]] = {}
    z_threshold = 1.0 + (req.sensitivity or 3.0) * 0.67 if req.sensitivity else 3.0

    if not isinstance(metrics_raw, Exception):
        series_list: List[Tuple[str, str, list, list]] = []
        baseline_tasks = []

        for query_string, resp in metrics_raw:
            for metric_name, ts, vals in anomaly.iter_series(resp):
                series_list.append((query_string, metric_name, ts, vals))
                baseline_tasks.append(
                    baseline_store.compute_and_persist(tenant_id, metric_name, ts, vals, z_threshold)
                )

        baselines = await asyncio.gather(*baseline_tasks, return_exceptions=True)

        for (query_string, metric_name, ts, vals), baseline in zip(series_list, baselines):
            if isinstance(baseline, Exception):
                from engine.baseline import compute as baseline_compute
                baseline = baseline_compute(ts, vals, z_threshold=z_threshold)

            metric_anomalies.extend(anomaly.detect(metric_name, ts, vals, req.sensitivity))
            change_points.extend(
                changepoint_detect(ts, vals, threshold_sigma=baseline.std or z_threshold)
            )
            series_map[metric_name] = vals

            threshold = next(
                (v for k, v in FORECAST_THRESHOLDS.items() if k in query_string), None
            )
            if threshold:
                f = forecast(metric_name, ts, vals, threshold, horizon_seconds=req.forecast_horizon_seconds)
                if f:
                    forecasts.append(f)

            deg = analyze_degradation(metric_name, ts, vals)
            if deg:
                degradation_signals.append(deg)

    log_bursts, log_patterns = [], []
    if not isinstance(logs_raw, Exception):
        log_bursts = logs.detect_bursts(logs_raw)
        log_patterns = logs.analyze(logs_raw)
    else:
        log.warning("Logs unavailable: %s", logs_raw)

    service_latency, error_propagation = [], []
    graph = DependencyGraph()
    if not isinstance(traces_raw, Exception):
        service_latency = traces.analyze(traces_raw, req.apdex_threshold_ms)
        error_propagation = traces.detect_propagation(traces_raw)
        graph.from_spans(traces_raw)
    else:
        log.warning("Traces unavailable: %s", traces_raw)

    target_svc = req.services[0] if req.services else "global"
    slo_alerts_raw = []
    if not isinstance(slo_errors_raw, Exception) and not isinstance(slo_total_raw, Exception):
        err_series = list(anomaly.iter_series(slo_errors_raw))
        tot_series = list(anomaly.iter_series(slo_total_raw))
        for (_, err_ts, err_vals), (_, _tot_ts, tot_vals) in zip(err_series, tot_series):
            slo_alerts_raw.extend(
                slo_evaluate(target_svc, err_vals, tot_vals, err_ts, req.slo_target or 0.999)
            )
    slo_alerts = [SloBurnAlertModel(**dataclasses.asdict(a)) for a in slo_alerts_raw]

    log_metric_links = link_logs_to_metrics(metric_anomalies, log_bursts)
    correlated_events = correlate(
        metric_anomalies,
        log_bursts,
        service_latency,
        window_seconds=req.correlation_window_seconds,
    )
    anomaly_clusters = cluster(metric_anomalies)

    fresh_granger = test_all_pairs(series_map, max_lag=3) if len(series_map) >= 2 else []
    service_label = req.services[0] if req.services else "global"
    await granger_store.save_and_merge(tenant_id, service_label, fresh_granger)

    causal_graph = CausalGraph()
    causal_graph.from_granger_results(fresh_granger)

    deployment_events = await registry.events_in_window(tenant_id, req.start, req.end)
    bayesian_scores = bayesian_score(
        has_deployment_event=bool(deployment_events),
        has_metric_spike=bool(metric_anomalies),
        has_log_burst=bool(log_bursts),
        has_latency_spike=bool(service_latency),
        has_error_propagation=bool(error_propagation),
    )

    compat_registry = _build_compat_registry(deployment_events)
    root_causes = rca.generate(
        metric_anomalies,
        log_bursts,
        log_patterns,
        service_latency,
        error_propagation,
        correlated_events=correlated_events,
        graph=graph,
        event_registry=compat_registry,
    )
    ranked_causes = rank(root_causes, correlated_events)

    pydantic_root_causes = []
    for r in ranked_causes:
        rc = r.root_cause
        if dataclasses.is_dataclass(rc):
            pyd = RootCauseModel(**dataclasses.asdict(rc))
        elif isinstance(rc, dict):
            pyd = RootCauseModel(**rc)
        else:
            pyd = RootCauseModel.model_validate(rc)
        pydantic_root_causes.append(pyd)

    severity = _overall_severity(
        metric_anomalies, log_bursts, log_patterns,
        service_latency, slo_alerts, forecasts,
    )

    report = AnalysisReport(
        tenant_id=tenant_id,
        start=req.start,
        end=req.end,
        duration_seconds=req.end - req.start,
        metric_anomalies=metric_anomalies,
        log_bursts=log_bursts,
        log_patterns=log_patterns,
        service_latency=service_latency,
        error_propagation=error_propagation,
        root_causes=pydantic_root_causes,
        ranked_causes=ranked_causes,
        slo_alerts=slo_alerts,
        change_points=change_points,
        log_metric_links=log_metric_links,
        forecasts=forecasts,
        degradation_signals=degradation_signals,
        anomaly_clusters=anomaly_clusters,
        granger_results=fresh_granger,
        bayesian_scores=bayesian_scores,
        overall_severity=severity,
        summary="",
    )
    report.summary = _summary(report)
    return report


def _build_compat_registry(deployment_events: list) -> EventRegistry:
    r = EventRegistry()
    for e in deployment_events:
        r.register(DeploymentEvent(
            service=e["service"],
            timestamp=e["timestamp"],
            version=e["version"],
            author=e.get("author", ""),
            environment=e.get("environment", "production"),
            source=e.get("source", "redis"),
            metadata=e.get("metadata", {}),
        ))
    return r