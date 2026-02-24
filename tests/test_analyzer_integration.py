"""
Integration and throughput tests for analyzer run path.
"""

import asyncio
import time

import pytest

from api.requests import AnalyzeRequest
from api.responses import MetricAnomaly
from engine import analyzer
from engine.baseline.compute import Baseline
from engine.enums import ChangeType, Severity


def _metric_result(name: str, values: list[float]) -> dict:
    ts = list(range(1, len(values) + 1))
    return {
        "status": "success",
        "data": {
            "result": [
                {
                    "metric": {"__name__": name},
                    "values": [[t, str(v)] for t, v in zip(ts, values)],
                }
            ]
        },
    }


class DummyProvider:
    async def query_logs(self, query: str, start: int, end: int, limit=None):
        dense = [(30 + i * 0.01, f"ERROR burst {i}") for i in range(100)]
        sparse = [(200 + i * 10, "normal") for i in range(20)]
        values = [[str(int(t * 1e9)), line] for t, line in dense + sparse]
        return {
            "data": {
                "result": [
                    {
                        "stream": {"service": "payment-service", "level": "error"},
                        "values": values,
                    }
                ]
            }
        }

    async def query_traces(self, filters, start: int, end: int, limit=None):
        traces = []
        for service in ("payment-service", "order-service"):
            for i in range(8):
                traces.append(
                    {
                        "rootServiceName": service,
                        "rootTraceName": f"{service}.op",
                        "durationMs": 6000.0 if i % 2 == 0 else 100.0,
                        "spanSet": {
                            "spans": [
                                {
                                    "attributes": [
                                        {"key": "status.code", "value": {"stringValue": "STATUS_CODE_ERROR" if i % 3 == 0 else "OK"}},
                                    ]
                                }
                            ]
                        },
                        "spanSets": [
                            {
                                "attributes": [
                                    {"key": "service.name", "value": {"stringValue": service}},
                                    {"key": "peer.service", "value": {"stringValue": "db"}},
                                ]
                            }
                        ],
                    }
                )
        return {"traces": traces}

    async def query_metrics(self, query: str, start: int, end: int, step: str):
        if query == analyzer.SLO_ERROR_QUERY:
            return _metric_result("slo_errors", [1.0] * 40)
        if query == analyzer.SLO_TOTAL_QUERY:
            return _metric_result("slo_total", [100.0] * 40)

        base = [1.0] * 40
        base[30] = 100.0
        return _metric_result("shared_metric", base)


class EmptyProvider:
    async def query_logs(self, query: str, start: int, end: int, limit=None):
        return {"data": {"result": []}}

    async def query_traces(self, filters, start: int, end: int, limit=None):
        return {"traces": []}

    async def query_metrics(self, query: str, start: int, end: int, step: str):
        return {"status": "success", "data": {"result": []}}


class DummyRegistry:
    async def events_in_window(self, tenant_id: str, start: int, end: int):
        return []


def fake_detect(metric_name, ts, vals, sensitivity=None):
    t = float(ts[len(ts) // 2])
    v = float(vals[len(vals) // 2])
    return [
        MetricAnomaly(
            metric_name=metric_name,
            timestamp=t,
            value=v,
            change_type=ChangeType.spike,
            z_score=5.0,
            mad_score=5.0,
            isolation_score=-0.5,
            expected_range=(0.0, 1.0),
            severity=Severity.high,
            description=f"{metric_name} spike",
        )
    ]


@pytest.mark.asyncio
async def test_analyzer_run_non_empty_path_and_tenant_isolation(monkeypatch):
    monkeypatch.setattr(analyzer, "DEFAULT_METRIC_QUERIES", ["q_a", "q_b"])
    monkeypatch.setattr(analyzer, "get_registry", lambda: DummyRegistry())
    monkeypatch.setattr(analyzer.anomaly, "detect", fake_detect)
    monkeypatch.setattr(analyzer, "changepoint_detect", lambda ts, vals, threshold_sigma=None: [])
    monkeypatch.setattr(analyzer, "test_all_pairs", lambda series_map, max_lag=None, p_threshold=None: [])

    captured = {"baseline_tenants": set(), "granger_tenants": set()}

    async def fake_compute_and_persist(tenant_id, metric_name, ts, vals, z_threshold=3.0):
        captured["baseline_tenants"].add(tenant_id)
        return Baseline(mean=1.0, std=1.0, lower=0.0, upper=2.0, sample_count=len(vals))

    async def fake_save_and_merge(tenant_id, service, fresh_results):
        captured["granger_tenants"].add(tenant_id)
        return []

    monkeypatch.setattr(analyzer.baseline_store, "compute_and_persist", fake_compute_and_persist)
    monkeypatch.setattr(analyzer.granger_store, "save_and_merge", fake_save_and_merge)

    req = AnalyzeRequest(tenant_id="tenant-one", start=1, end=3600, step="15s", services=["payment-service"])
    report = await analyzer.run(DummyProvider(), req)

    assert report.tenant_id == "tenant-one"
    assert report.log_bursts
    assert report.metric_anomalies
    assert report.service_latency
    assert report.summary
    assert isinstance(report.analysis_warnings, list)
    assert captured["baseline_tenants"] == {"tenant-one"}
    assert captured["granger_tenants"] == {"tenant-one"}


@pytest.mark.asyncio
async def test_analyzer_concurrent_throughput_target(monkeypatch):
    monkeypatch.setattr(analyzer, "DEFAULT_METRIC_QUERIES", ["q_a", "q_b"])
    monkeypatch.setattr(analyzer, "get_registry", lambda: DummyRegistry())
    monkeypatch.setattr(analyzer.anomaly, "detect", fake_detect)
    monkeypatch.setattr(analyzer, "changepoint_detect", lambda ts, vals, threshold_sigma=None: [])
    monkeypatch.setattr(analyzer, "test_all_pairs", lambda series_map, max_lag=None, p_threshold=None: [])

    async def fake_compute_and_persist(tenant_id, metric_name, ts, vals, z_threshold=3.0):
        return Baseline(mean=1.0, std=1.0, lower=0.0, upper=2.0, sample_count=len(vals))

    async def fake_save_and_merge(tenant_id, service, fresh_results):
        return []

    monkeypatch.setattr(analyzer.baseline_store, "compute_and_persist", fake_compute_and_persist)
    monkeypatch.setattr(analyzer.granger_store, "save_and_merge", fake_save_and_merge)

    req = AnalyzeRequest(tenant_id="tenant-perf", start=1, end=3600, step="15s", services=["payment-service"])

    async def _timed_run():
        t0 = time.perf_counter()
        await analyzer.run(DummyProvider(), req)
        return time.perf_counter() - t0

    durations = await asyncio.gather(*[_timed_run() for _ in range(5)])
    durations_sorted = sorted(durations)
    p95_index = max(0, int(round(0.95 * len(durations_sorted))) - 1)
    p95 = durations_sorted[p95_index]
    assert p95 < 1.5


@pytest.mark.asyncio
async def test_analyzer_empty_inputs_returns_safe_report(monkeypatch):
    monkeypatch.setattr(analyzer, "DEFAULT_METRIC_QUERIES", ["q_a"])
    monkeypatch.setattr(analyzer, "get_registry", lambda: DummyRegistry())

    req = AnalyzeRequest(tenant_id="tenant-empty", start=1, end=3600, step="15s", services=["payment-service"])
    report = await analyzer.run(EmptyProvider(), req)

    assert report.tenant_id == "tenant-empty"
    assert report.metric_anomalies == []
    assert report.log_bursts == []
    assert report.service_latency == []
    assert report.root_causes == []
    assert "No anomalies detected" in report.summary
    assert any("returned no entries" in warning or "returned no traces" in warning for warning in report.analysis_warnings)


@pytest.mark.asyncio
async def test_analyzer_enforces_caps_during_run(monkeypatch):
    monkeypatch.setattr(analyzer, "DEFAULT_METRIC_QUERIES", ["q_a", "q_b", "q_c"])
    monkeypatch.setattr(analyzer, "get_registry", lambda: DummyRegistry())
    monkeypatch.setattr(analyzer.anomaly, "detect", fake_detect)
    monkeypatch.setattr(analyzer, "changepoint_detect", lambda ts, vals, threshold_sigma=None: [])
    monkeypatch.setattr(analyzer, "test_all_pairs", lambda series_map, max_lag=None, p_threshold=None: [])
    monkeypatch.setattr("config.settings.analyzer_max_metric_anomalies", 2)
    monkeypatch.setattr("config.settings.analyzer_max_root_causes", 1)
    monkeypatch.setattr("config.settings.analyzer_max_granger_pairs", 1)
    monkeypatch.setattr("config.settings.analyzer_max_clusters", 1)
    monkeypatch.setattr("config.settings.analyzer_max_change_points", 1)

    async def fake_compute_and_persist(tenant_id, metric_name, ts, vals, z_threshold=3.0):
        return Baseline(mean=1.0, std=1.0, lower=0.0, upper=2.0, sample_count=len(vals))

    async def fake_save_and_merge(tenant_id, service, fresh_results):
        return []

    monkeypatch.setattr(analyzer.baseline_store, "compute_and_persist", fake_compute_and_persist)
    monkeypatch.setattr(analyzer.granger_store, "save_and_merge", fake_save_and_merge)

    req = AnalyzeRequest(tenant_id="tenant-cap", start=1, end=3600, step="15s", services=["payment-service"])
    report = await analyzer.run(DummyProvider(), req)
    assert len(report.metric_anomalies) <= 2
    assert len(report.root_causes) <= 1
    assert len(report.ranked_causes) <= 1
    assert len(report.anomaly_clusters) <= 1
    assert len(report.granger_results) <= 1
    assert any("capped" in warning for warning in report.analysis_warnings)
