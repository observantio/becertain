"""
Analyzer Module for Root Cause Analysis and Correlation of Anomalies

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import math
import time
from typing import Dict, List, Tuple, cast

import numpy as np

from datasources.provider import DataSourceProvider
from engine import anomaly, logs, rca, traces
from engine.baseline import compute as baseline_compute
from engine.causal import CausalGraph, bayesian_score, test_all_pairs
from engine.changepoint import detect as changepoint_detect, ChangePoint
from config import DEFAULT_METRIC_QUERIES, FORECAST_THRESHOLDS, SLO_ERROR_QUERY, SLO_TOTAL_QUERY, settings
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
from engine.enums import Severity, Signal

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
        parts.append(f"{len(group_metric_anomalies(report.metric_anomalies))} metric anomaly group(s)")
    if report.log_bursts:
        parts.append(f"{len(report.log_bursts)} log burst(s)")
    if report.log_patterns:
        hi_count = sum(p.count for p in report.log_patterns if p.severity.weight() >= 3)
        if hi_count:
            parts.append(f"{hi_count} high/critical log events")
    if report.service_latency:
        parts.append(f"{len(report.service_latency)} service(s) degraded")
    if report.error_propagation:
        parts.append(f"error propagation from {report.error_propagation[0].source_service}")
    if report.slo_alerts:
        parts.append(f"{len(report.slo_alerts)} SLO burn alert(s)")
    if report.change_points:
        parts.append(f"{len(report.change_points)} change point(s)")
    if report.forecasts:
        critical = sum(1 for f in report.forecasts if f.severity.weight() >= 4)
        if critical:
            parts.append(f"{critical} imminent breach(es) predicted")
    if report.degradation_signals:
        parts.append(f"{len(report.degradation_signals)} degrading metric(s)")

    if not parts:
        return "No anomalies detected in the analysis window."

    top = f" Top: {report.root_causes[0].hypothesis[:120]}..." if report.root_causes else ""
    return f"[{report.overall_severity.value.upper()}] {' | '.join(parts)}.{top}"


def _to_root_cause_model(rc) -> RootCauseModel:
    def _normalize_signals(values: list) -> list[Signal]:
        normalized: list[Signal] = []
        for raw in values:
            if isinstance(raw, Signal):
                normalized.append(raw)
                continue
            text = str(raw).lower()
            if text.startswith("metric"):
                normalized.append(Signal.metrics)
            elif text.startswith("log"):
                normalized.append(Signal.logs)
            elif text.startswith("trace"):
                normalized.append(Signal.traces)
            elif text.startswith("event") or text.startswith("deploy"):
                normalized.append(Signal.events)
        return list(dict.fromkeys(normalized))

    def _normalize_payload(payload: dict) -> dict:
        signals = payload.get("contributing_signals")
        if isinstance(signals, list):
            payload["contributing_signals"] = _normalize_signals(signals)
        confidence: object = payload.get("confidence", 0.0)
        if isinstance(confidence, (int, float, str)):
            try:
                confidence_value = float(confidence)
            except ValueError:
                confidence_value = 0.0
        else:
            confidence_value = 0.0
        if not math.isfinite(confidence_value):
            confidence_value = 0.0
        payload["confidence"] = max(0.0, min(1.0, confidence_value))
        return payload

    if dataclasses.is_dataclass(rc) and not isinstance(rc, type):
        return RootCauseModel(**_normalize_payload(dataclasses.asdict(rc)))
    if isinstance(rc, dict):
        return RootCauseModel(**_normalize_payload(dict(rc)))
    return RootCauseModel.model_validate(rc)


def _build_compat_registry(deployment_events: list) -> EventRegistry:
    registry = EventRegistry()
    for e in deployment_events:
        registry.register(DeploymentEvent(
            service=e["service"],
            timestamp=e["timestamp"],
            version=e["version"],
            author=e.get("author", ""),
            environment=e.get("environment", "production"),
            source=e.get("source", "redis"),
            metadata=e.get("metadata", {}),
        ))
    return registry


def _series_key(query_string: str, metric_name: str) -> str:
    return f"{query_string}::{metric_name}"


def _trim_to_len(values: list[float], target_len: int) -> list[float]:
    if len(values) == target_len:
        return values
    return values[:target_len]


def _dedupe_metric_anomalies(items: list) -> list:
    selected: dict[tuple[str, int, str], object] = {}
    for item in items:
        key = (
            str(getattr(item, "metric_name", "metric")),
            int(round(float(getattr(item, "timestamp", 0.0)))),
            str(getattr(getattr(item, "change_type", None), "value", getattr(item, "change_type", "unknown"))),
        )
        current = selected.get(key)
        if current is None:
            selected[key] = item
            continue
        curr_sev = getattr(current, "severity", Severity.low).weight()
        next_sev = getattr(item, "severity", Severity.low).weight()
        if next_sev > curr_sev:
            selected[key] = item
            continue
        if next_sev == curr_sev:
            if abs(float(getattr(item, "z_score", 0.0))) > abs(float(getattr(current, "z_score", 0.0))):
                selected[key] = item
    return sorted(selected.values(), key=lambda a: (a.timestamp, a.metric_name))


def _dedupe_change_points(items: List[ChangePoint]) -> List[ChangePoint]:
    selected: dict[tuple[str, int, str], ChangePoint] = {}
    for item in items:
        key = (
            str(getattr(item, "metric_name", "metric")),
            int(round(float(item.timestamp))),
            str(getattr(item.change_type, "value", item.change_type)),
        )
        current = selected.get(key)
        if current is None or float(item.magnitude) > float(current.magnitude):
            selected[key] = item
    return sorted(selected.values(), key=lambda c: (c.timestamp, c.metric_name))


def _dedupe_by_metric_with_severity(items: list) -> list:
    selected: dict[str, object] = {}
    for item in items:
        metric_name = str(getattr(item, "metric_name", "metric")).strip() or "metric"
        current = selected.get(metric_name)
        if current is None:
            selected[metric_name] = item
            continue
        curr_sev = getattr(getattr(current, "severity", Severity.low), "weight", lambda: 0)()
        next_sev = getattr(getattr(item, "severity", Severity.low), "weight", lambda: 0)()
        if next_sev > curr_sev:
            selected[metric_name] = item
            continue
        if next_sev == curr_sev:
            curr_signal = abs(float(getattr(current, "degradation_rate", getattr(current, "slope_per_second", 0.0))))
            next_signal = abs(float(getattr(item, "degradation_rate", getattr(item, "slope_per_second", 0.0))))
            if next_signal > curr_signal:
                selected[metric_name] = item
    return sorted(
        selected.values(),
        key=lambda item: (
            -getattr(getattr(item, "severity", Severity.low), "weight", lambda: 0)(),
            str(getattr(item, "metric_name", "metric")),
        ),
    )


def _cap_list(items: list, limit: int, key_func, reverse: bool = True) -> list:
    capped_limit = max(1, int(limit))
    if len(items) <= capped_limit:
        return items
    return sorted(items, key=key_func, reverse=reverse)[:capped_limit]


def _limit_analyzer_output(
    *,
    metric_anomalies: list,
    change_points: List[ChangePoint],
    root_causes: list[RootCauseModel],
    ranked_causes: list,
    anomaly_clusters: list,
    granger_results: list,
    warnings: list[str],
) -> tuple[list, List[ChangePoint], list[RootCauseModel], list, list, list]:
    metric_anomalies_limited = _cap_list(
        metric_anomalies,
        settings.analyzer_max_metric_anomalies,
        key_func=lambda item: (
            getattr(getattr(item, "severity", Severity.low), "weight", lambda: 0)(),
            abs(float(getattr(item, "z_score", 0.0))),
            float(getattr(item, "timestamp", 0.0)),
        ),
    )
    if len(metric_anomalies_limited) < len(metric_anomalies):
        warnings.append(
            f"Metric anomalies capped to top {len(metric_anomalies_limited)} from {len(metric_anomalies)} "
            "by severity and z-score."
        )

    change_points_limited = _cap_list(
        change_points,
        settings.analyzer_max_change_points,
        key_func=lambda item: (float(getattr(item, "magnitude", 0.0)), float(getattr(item, "timestamp", 0.0))),
    )
    if len(change_points_limited) < len(change_points):
        warnings.append(
            f"Change points capped to top {len(change_points_limited)} from {len(change_points)} by magnitude."
        )

    root_causes_limited = _cap_list(
        root_causes,
        settings.analyzer_max_root_causes,
        key_func=lambda item: float(getattr(item, "confidence", 0.0)),
    )
    if len(root_causes_limited) < len(root_causes):
        warnings.append(f"Root causes capped to top {len(root_causes_limited)} by confidence.")

    ranked_limited = _cap_list(
        ranked_causes,
        settings.analyzer_max_root_causes,
        key_func=lambda item: float(getattr(item, "final_score", 0.0)),
    )

    clusters_limited = _cap_list(
        anomaly_clusters,
        settings.analyzer_max_clusters,
        key_func=lambda item: int(getattr(item, "size", 0)),
    )
    if len(clusters_limited) < len(anomaly_clusters):
        warnings.append(f"Anomaly clusters capped to top {len(clusters_limited)} by size.")

    granger_limited = _cap_list(
        granger_results,
        settings.analyzer_max_granger_pairs,
        key_func=lambda item: float(getattr(item, "strength", 0.0)),
    )
    if len(granger_limited) < len(granger_results):
        warnings.append(f"Granger pairs capped to top {len(granger_limited)} by strength.")

    return (
        metric_anomalies_limited,
        change_points_limited,
        root_causes_limited,
        ranked_limited,
        clusters_limited,
        granger_limited,
    )


async def _process_one_metric_series(
    req: AnalyzeRequest,
    query_string: str,
    metric_name: str,
    ts: list[float],
    vals: list[float],
    z_threshold: float,
):
    try:
        baseline = await baseline_store.compute_and_persist(req.tenant_id, metric_name, ts, vals, z_threshold)
    except Exception:
        baseline = baseline_compute(ts, vals, z_threshold=z_threshold)

    metric_anomalies = anomaly.detect(metric_name, ts, vals, req.sensitivity)
    try:
        change_points = changepoint_detect(ts, vals, baseline.std or z_threshold, metric_name=metric_name)
    except TypeError:
        # Backward-compatible path for monkeypatched/legacy detector signatures.
        change_points = changepoint_detect(ts, vals, baseline.std or z_threshold)

    threshold = next((v for k, v in FORECAST_THRESHOLDS.items() if k in query_string), None)
    if threshold:
        fc = forecast(metric_name, ts, vals, threshold, req.forecast_horizon_seconds)
    else:
        fc = None

    deg = analyze_degradation(metric_name, ts, vals)

    return metric_anomalies, change_points, fc, deg


async def _process_metrics(
    provider: DataSourceProvider,
    req: AnalyzeRequest,
    all_metric_queries: List[str],
    z_threshold: float,
) -> Tuple[list, List[ChangePoint], list, list, Dict[str, List[float]]]:
    metrics_raw = await fetch_metrics(provider, all_metric_queries, req.start, req.end, req.step)

    series_list: List[Tuple[str, str, list, list]] = [
        (query_string, metric_name, ts, vals)
        for query_string, resp in metrics_raw
        for metric_name, ts, vals in anomaly.iter_series(resp, query_hint=query_string)
    ]

    tasks = [
        _process_one_metric_series(req, query_string, metric_name, ts, vals, z_threshold)
        for query_string, metric_name, ts, vals in series_list
    ]
    processed = await asyncio.gather(*tasks, return_exceptions=True)

    metric_anomalies: list = []
    change_points: List[ChangePoint] = []
    forecasts: list = []
    degradation_signals: list = []
    series_map: Dict[str, List[float]] = {}

    for (query_string, metric_name, _ts, vals), result in zip(series_list, processed):
        series_map[_series_key(query_string, metric_name)] = vals
        if isinstance(result, BaseException):
            log.warning("Metric stage failed for %s (%s): %s", metric_name, query_string, result)
            continue
        metric_stage_anomalies, metric_stage_changes, fc, deg = cast(tuple[list, list, object, object], result)
        metric_anomalies.extend(metric_stage_anomalies)
        change_points.extend(metric_stage_changes)
        if fc:
            forecasts.append(fc)
        if deg:
            degradation_signals.append(deg)

    return metric_anomalies, change_points, forecasts, degradation_signals, series_map


def _slo_series_pairs(err_raw, tot_raw, warnings: list[str]) -> list[tuple[list[float], list[float], list[float]]]:
    err_series = list(anomaly.iter_series(err_raw, query_hint=SLO_ERROR_QUERY))
    tot_series = list(anomaly.iter_series(tot_raw, query_hint=SLO_TOTAL_QUERY))

    if len(err_series) != len(tot_series):
        warnings.append(
            f"SLO series mismatch: errors={len(err_series)} totals={len(tot_series)}. "
            f"Using first {min(len(err_series), len(tot_series))} pair(s)."
        )

    pairs = []
    for idx in range(min(len(err_series), len(tot_series))):
        _, err_ts, err_vals = err_series[idx]
        _, _tot_ts, tot_vals = tot_series[idx]
        if len(err_vals) != len(tot_vals):
            n = min(len(err_vals), len(tot_vals))
            warnings.append(f"SLO sample length mismatch at pair {idx}: errors={len(err_vals)} totals={len(tot_vals)}.")
            err_vals = _trim_to_len(err_vals, n)
            tot_vals = _trim_to_len(tot_vals, n)
            err_ts = _trim_to_len(err_ts, n)
        if err_vals and tot_vals and err_ts:
            pairs.append((err_ts, err_vals, tot_vals))
    return pairs


def _select_granger_series(series_map: Dict[str, List[float]]) -> Dict[str, List[float]]:
    min_samples = max(2, int(settings.analyzer_granger_min_samples))
    max_series = max(2, int(settings.analyzer_granger_max_series))

    eligible: list[tuple[str, float]] = []
    for name, values in series_map.items():
        arr = np.array(values, dtype=float)
        finite = arr[np.isfinite(arr)]
        if finite.size < min_samples:
            continue
        var = float(np.var(finite))
        if var <= 0:
            continue
        eligible.append((name, var))

    eligible.sort(key=lambda x: x[1], reverse=True)
    selected_names = {name for name, _ in eligible[:max_series]}
    return {name: vals for name, vals in series_map.items() if name in selected_names}


async def run(provider: DataSourceProvider, req: AnalyzeRequest) -> AnalysisReport:
    started = time.perf_counter()
    registry = get_registry()
    tenant_id = req.tenant_id
    primary_service = req.services[0] if req.services else None
    warnings: list[str] = []

    log_query = req.log_query or (
        '{service=~"' + "|".join(req.services) + '"}' if req.services else '{job=~".+"}'
    )
    trace_filters = {"service.name": primary_service} if primary_service else {}
    all_metric_queries = list(dict.fromkeys((req.metric_queries or []) + DEFAULT_METRIC_QUERIES))

    if req.sensitivity:
        z_threshold = 1.0 + req.sensitivity * settings.analyzer_sensitivity_factor
    else:
        z_threshold = settings.baseline_zscore_threshold

    fetch_started = time.perf_counter()
    try:
        logs_raw, traces_raw, slo_errors_raw, slo_total_raw = await asyncio.wait_for(
            asyncio.gather(
                provider.query_logs(
                    query=log_query,
                    start=req.start * 1_000_000_000,
                    end=req.end * 1_000_000_000,
                ),
                provider.query_traces(filters=trace_filters, start=req.start, end=req.end),
                provider.query_metrics(query=SLO_ERROR_QUERY, start=req.start, end=req.end, step=req.step),
                provider.query_metrics(query=SLO_TOTAL_QUERY, start=req.start, end=req.end, step=req.step),
                return_exceptions=True,
            ),
            timeout=float(settings.analyzer_fetch_timeout_seconds),
        )
    except TimeoutError:
        warnings.append(
            f"Fetch stage timed out after {settings.analyzer_fetch_timeout_seconds}s; "
            "continuing with best-effort analysis."
        )
        logs_raw = TimeoutError("logs fetch timeout")
        traces_raw = TimeoutError("traces fetch timeout")
        slo_errors_raw = TimeoutError("slo error fetch timeout")
        slo_total_raw = TimeoutError("slo total fetch timeout")
    log.debug("analyzer stage=fetch duration=%.4fs", time.perf_counter() - fetch_started)

    metrics_started = time.perf_counter()
    try:
        metric_anomalies, change_points, forecasts, degradation_signals, series_map = await asyncio.wait_for(
            _process_metrics(provider, req, all_metric_queries, z_threshold),
            timeout=float(settings.analyzer_metrics_timeout_seconds),
        )
    except TimeoutError:
        msg = (
            f"Metrics stage timed out after {settings.analyzer_metrics_timeout_seconds}s; "
            "returning partial report."
        )
        warnings.append(msg)
        log.warning(msg)
        metric_anomalies, change_points, forecasts, degradation_signals, series_map = [], [], [], [], {}
    except Exception as exc:
        msg = f"Metrics unavailable: {exc}"
        warnings.append(msg)
        log.warning(msg)
        metric_anomalies, change_points, forecasts, degradation_signals, series_map = [], [], [], [], {}
    raw_metric_anomaly_count = len(metric_anomalies)
    raw_change_point_count = len(change_points)
    metric_anomalies = _dedupe_metric_anomalies(metric_anomalies)
    change_points = _dedupe_change_points(change_points)
    forecasts = _dedupe_by_metric_with_severity(forecasts)
    degradation_signals = _dedupe_by_metric_with_severity(degradation_signals)
    if raw_metric_anomaly_count > len(metric_anomalies):
        warnings.append(
            f"Deduplicated metric anomalies from {raw_metric_anomaly_count} to {len(metric_anomalies)} "
            "to reduce duplicate series noise."
        )
    if raw_change_point_count > len(change_points):
        warnings.append(
            f"Deduplicated change points from {raw_change_point_count} to {len(change_points)} "
            "to reduce duplicate series noise."
        )
    log.debug("analyzer stage=metrics duration=%.4fs", time.perf_counter() - metrics_started)

    logs_started = time.perf_counter()
    log_bursts, log_patterns = [], []
    if isinstance(logs_raw, dict):
        log_bursts = logs.detect_bursts(logs_raw)
        log_patterns = logs.analyze(logs_raw)
        if not logs_raw.get("data", {}).get("result"):
            warnings.append("Logs query returned no entries in the selected window.")
    elif isinstance(logs_raw, Exception):
        msg = f"Logs unavailable: {logs_raw}"
        warnings.append(msg)
        log.warning(msg)
    else:
        msg = f"Logs unavailable: unsupported response type {type(logs_raw).__name__}"
        warnings.append(msg)
        log.warning(msg)
    log.debug("analyzer stage=logs duration=%.4fs", time.perf_counter() - logs_started)

    traces_started = time.perf_counter()
    service_latency, error_propagation = [], []
    graph = DependencyGraph()
    if isinstance(traces_raw, dict):
        service_latency = traces.analyze(traces_raw, req.apdex_threshold_ms)
        error_propagation = traces.detect_propagation(traces_raw)
        graph.from_spans(traces_raw)
        if not traces_raw.get("traces"):
            warnings.append("Trace query returned no traces; topology and propagation insights are limited.")
    elif isinstance(traces_raw, Exception):
        msg = f"Traces unavailable: {traces_raw}"
        warnings.append(msg)
        log.warning(msg)
    else:
        msg = f"Traces unavailable: unsupported response type {type(traces_raw).__name__}"
        warnings.append(msg)
        log.warning(msg)
    log.debug("analyzer stage=traces duration=%.4fs", time.perf_counter() - traces_started)

    slo_started = time.perf_counter()
    slo_alerts_raw = []
    if not isinstance(slo_errors_raw, Exception) and not isinstance(slo_total_raw, Exception):
        for err_ts, err_vals, tot_vals in _slo_series_pairs(slo_errors_raw, slo_total_raw, warnings):
            slo_alerts_raw.extend(
                slo_evaluate(primary_service or "global", err_vals, tot_vals, err_ts, req.slo_target or 0.999)
            )
    else:
        warnings.append("SLO metrics unavailable for one or both queries.")
    slo_alerts = [SloBurnAlertModel(**dataclasses.asdict(a)) for a in slo_alerts_raw]
    log.debug("analyzer stage=slo duration=%.4fs", time.perf_counter() - slo_started)

    correlate_started = time.perf_counter()
    log_metric_links = link_logs_to_metrics(metric_anomalies, log_bursts)
    correlated_events = correlate(
        metric_anomalies,
        log_bursts,
        service_latency,
        window_seconds=req.correlation_window_seconds,
    )
    anomaly_clusters = cluster(metric_anomalies)
    log.debug("analyzer stage=correlate duration=%.4fs", time.perf_counter() - correlate_started)

    causal_started = time.perf_counter()
    series_for_granger = _select_granger_series(series_map)
    granger_started = time.perf_counter()
    fresh_granger = test_all_pairs(series_for_granger, max_lag=settings.granger_max_lag) if len(series_for_granger) >= 2 else []
    granger_elapsed = time.perf_counter() - granger_started
    if granger_elapsed > float(settings.analyzer_causal_timeout_seconds):
        warnings.append(
            f"Causal granger stage exceeded target {settings.analyzer_causal_timeout_seconds}s "
            f"(actual {granger_elapsed:.2f}s)."
        )

    try:
        await asyncio.wait_for(
            granger_store.save_and_merge(tenant_id, primary_service or "global", fresh_granger),
            timeout=1.0,
        )
    except Exception as exc:
        warnings.append(f"Failed to persist granger results: {exc}")

    causal_graph = CausalGraph()
    causal_graph.from_granger_results(fresh_granger)

    deployment_events = cast(list[dict], await registry.events_in_window(tenant_id, req.start, req.end))
    bayesian_scores = bayesian_score(
        has_deployment_event=bool(deployment_events),
        has_metric_spike=bool(metric_anomalies),
        has_log_burst=bool(log_bursts),
        has_latency_spike=bool(service_latency),
        has_error_propagation=bool(error_propagation),
    )

    root_causes = rca.generate(
        metric_anomalies,
        log_bursts,
        log_patterns,
        service_latency,
        error_propagation,
        correlated_events=correlated_events,
        graph=graph,
        event_registry=_build_compat_registry(deployment_events),
    )
    ranked_causes = rank(root_causes, correlated_events)
    pydantic_root_causes: list[RootCauseModel] = []
    ranked_valid: list = []
    for item in ranked_causes:
        try:
            pydantic_root_causes.append(_to_root_cause_model(item.root_cause))
            ranked_valid.append(item)
        except Exception as exc:
            warnings.append(f"Dropped invalid root cause model during normalization: {exc}")
    ranked_causes = ranked_valid
    (
        metric_anomalies,
        change_points,
        pydantic_root_causes,
        ranked_causes,
        anomaly_clusters,
        fresh_granger,
    ) = _limit_analyzer_output(
        metric_anomalies=metric_anomalies,
        change_points=change_points,
        root_causes=pydantic_root_causes,
        ranked_causes=ranked_causes,
        anomaly_clusters=anomaly_clusters,
        granger_results=fresh_granger,
        warnings=warnings,
    )
    log.debug("analyzer stage=causal duration=%.4fs", time.perf_counter() - causal_started)

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
        analysis_warnings=warnings,
        overall_severity=severity,
        summary="",
    )
    report.summary = _summary(report)
    log.info(
        "analyzer done tenant=%s service=%s duration=%.4fs warnings=%d",
        tenant_id,
        primary_service or "global",
        time.perf_counter() - started,
        len(warnings),
    )
    return report
