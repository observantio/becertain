"""
Test cases for correlation logic in the analysis engine, validating temporal correlation of anomalies, log bursts, and service latency, as well as edge cases in timestamp handling and relevance filtering.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from engine.correlation.temporal import CorrelatedEvent, correlate
from engine.correlation.signals import link_logs_to_metrics
from api.responses import MetricAnomaly, LogBurst, ServiceLatency
from engine.enums import Severity, ChangeType


def make_anomaly(t):
    return MetricAnomaly(
        metric_name="m", timestamp=t, value=1,
        change_type=ChangeType.spike, z_score=1, mad_score=1,
        isolation_score=0, expected_range=(0,1), severity=Severity.low,
        description=""
    )


def make_logburst(start, end):
    return LogBurst(
        window_start=start, window_end=end,
        rate_per_second=1, baseline_rate=1, ratio=1, severity=Severity.low
    )


def make_latency():
    return ServiceLatency(
        service="s", operation="o", p50_ms=10, p95_ms=20, p99_ms=30,
        apdex=0.5, error_rate=0, sample_count=1, severity=Severity.low
    )


def test_correlate_simple():
    anomalies = [make_anomaly(0), make_anomaly(100)]
    bursts = [make_logburst(0, 10)]
    sl = [make_latency()]
    events = correlate(anomalies, bursts, sl, window_seconds=200)
    assert isinstance(events, list)
    assert isinstance(events, list)
    assert events and isinstance(events[0], CorrelatedEvent)


def test_correlate_empty():
    assert correlate([], [], [], window_seconds=10) == []


def test_link_logs_to_metrics_uses_window_start_fields():
    links = link_logs_to_metrics([make_anomaly(10)], [make_logburst(9, 11)], max_lag_seconds=20)
    assert links
    assert links[0].log_stream == "unknown"


def test_correlate_ignores_invalid_logburst_timestamps():
    anomalies = [make_anomaly(100)]

    class BrokenBurst:
        start = "bad"
        end = "bad"

    bursts = [BrokenBurst()]
    events = correlate(anomalies, bursts, [], window_seconds=30)
    assert events == []


def test_correlate_only_links_temporally_and_name_relevant_latency():
    anomalies = [
        MetricAnomaly(
            metric_name="system_memory_usage_bytes{service=checkout}",
            timestamp=100,
            value=1,
            change_type=ChangeType.spike,
            z_score=4,
            mad_score=4,
            isolation_score=0,
            expected_range=(0, 1),
            severity=Severity.high,
            description="",
        )
    ]
    bursts = [make_logburst(95, 105)]
    latency = [
        ServiceLatency(
            service="checkout", operation="o", p50_ms=10, p95_ms=20, p99_ms=30,
            apdex=0.5, error_rate=0, sample_count=1, severity=Severity.low
        ),
        ServiceLatency(
            service="inventory", operation="o", p50_ms=10, p95_ms=20, p99_ms=30,
            apdex=0.5, error_rate=0, sample_count=1, severity=Severity.low
        ),
    ]
    events = correlate(anomalies, bursts, latency, window_seconds=30)
    assert events
    assert [s.service for s in events[0].service_latency] == ["checkout"]
