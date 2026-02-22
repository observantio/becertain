import pytest

from engine.rca.hypothesis import _signals_from_event, _action_for_category, generate, RootCause
from engine.enums import RcaCategory, Severity, ChangeType
from engine.correlation.temporal import CorrelatedEvent
from api.responses import MetricAnomaly, ServiceLatency


class DummyEvent:
    def __init__(self):
        self.metric_anomalies = []
        self.log_bursts = []
        self.service_latency = []
        self.window_start = 0
        self.confidence = 1.0


def test_signals_and_actions():
    ev = DummyEvent()
    ev.metric_anomalies = [MetricAnomaly(
        metric_id="m", metric_name="m", timestamp=1, value=0,
        change_type=ChangeType.spike,
        z_score=5, mad_score=2, isolation_score=0.0,
        expected_range=(0, 1), severity=Severity.high,
        description=""
    )]
    ev.log_bursts = []
    ev.service_latency = []
    signals = _signals_from_event(ev)
    # we should at least see a metrics signal when an anomaly exists
    assert "metrics" in signals
    assert "deployment" in _action_for_category(RcaCategory.deployment)
    assert "resource" in _action_for_category(RcaCategory.resource_exhaustion)
    assert "Investigate" in _action_for_category(None)


def test_generate_empty():
    root = generate([], [], [], [], [], correlated_events=[], graph=None, event_registry=None)
    assert root == []


def test_generate_with_simple_event():
    # build a minimal correlated event structure
    anomaly = MetricAnomaly(
        metric_id="m", metric_name="m", timestamp=1, value=100,
        change_type=ChangeType.spike,
        z_score=10, mad_score=5, isolation_score=0.0,
        expected_range=(0, 1), severity=Severity.high,
        description=""
    )]
    ev = CorrelatedEvent(
        window_start=1,
        window_end=2,
        metric_anomalies=[anomaly],
        log_bursts=[],
        service_latency=[ServiceLatency(
            service="svc",
            operation="op",
            p50_ms=50.0,
            p95_ms=80.0,
            p99_ms=100.0,
            apdex=0.9,
            error_rate=0.0,
            sample_count=1,
            severity=Severity.low,
        )],
        confidence=0.5,
    )
    root = generate([], [], [], [], [], correlated_events=[ev], graph=None, event_registry=None)
    assert isinstance(root, list)
    if root:
        assert isinstance(root[0], RootCause)
