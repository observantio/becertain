"""
Test Suite for Correlation Logic

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import pytest

from engine.correlation.temporal import CorrelatedEvent, correlate
from api.responses import MetricAnomaly, LogBurst, ServiceLatency
from engine.enums import Severity


def make_anomaly(t):
    return MetricAnomaly(
        metric_id="m", metric_name="m", timestamp=t, value=1,
        change_type="spike", z_score=1, mad_score=1,
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
