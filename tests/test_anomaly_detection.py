"""
Test cases for anomaly detection logic in the analysis engine, including output limiting and Granger causality series selection.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import pytest
import numpy as np

from api.responses import MetricAnomaly
from engine.anomaly.detection import (
    _apply_density_cap,
    _mad_scores,
    _cusum_changepoints,
    _change_type,
    _severity,
    _compress_runs,
    detect,
)
from engine.enums import ChangeType, Severity


def test_mad_and_cusum():
    arr = [1, 1, 1, 10, 1, 1, 1]
    m = _mad_scores(np.array(arr))
    assert m.dtype in (float, 'float64', 'int64')
    flags_hi = _cusum_changepoints(np.array(arr), threshold=100)
    assert not flags_hi.any()
    flags_lo = _cusum_changepoints(np.array(arr), threshold=0.1)
    assert flags_lo.any()


def test_change_type_severity():
    assert _change_type(10, 0, 1, 0) == ChangeType.spike
    assert _change_type(0, 0, -1, 0) == ChangeType.drop
    assert _change_type(0, 0, 0, 1) == ChangeType.drift
    sev = _severity(5, 0, -1)
    assert sev in (Severity.high, Severity.critical)
    assert _severity(0, 0, 0) == Severity.low


def test_detect_simple():
    ts = list(range(20))
    vals = [1]*19 + [100]
    anomalies = detect("m", ts, vals)
    assert isinstance(anomalies, list)
    if anomalies:
        assert hasattr(anomalies[0], 'change_type')


def test_compress_runs_limits_noisy_sequences(monkeypatch):
    monkeypatch.setattr("config.settings.anomaly_run_keep_max", 3)
    items = [
        MetricAnomaly(
            metric_name="m",
            timestamp=float(i),
            value=float(i),
            change_type=ChangeType.spike,
            z_score=2.5 + i * 0.1,
            mad_score=2.0,
            isolation_score=-0.5,
            expected_range=(0.0, 1.0),
            severity=Severity.high,
            description="",
        )
        for i in range(10)
    ]
    compressed = _compress_runs(items)
    assert len(compressed) <= 3
    assert compressed[0].timestamp == 0.0
    assert compressed[-1].timestamp == 9.0


def test_detect_filters_non_finite_points():
    ts = [1, 2, 3, 4, 5, 6, 7, 8]
    vals = [1.0, 1.0, float("nan"), 1.0, float("inf"), 1.0, 20.0, 1.0]
    anomalies = detect("m", ts, vals, sensitivity=3.0)
    assert all(a.timestamp == a.timestamp for a in anomalies)
    assert all(a.value == a.value for a in anomalies)


def test_detect_requires_statistical_or_multisignal_corroboration_for_iso(monkeypatch):
    class FakeIsolationForest:
        def __init__(self, *args, **kwargs):
            pass

        def fit_predict(self, x):
            import numpy as np
            return np.full(shape=(x.shape[0],), fill_value=-1, dtype=int)

        def score_samples(self, x):
            import numpy as np
            return np.full(shape=(x.shape[0],), fill_value=-0.8, dtype=float)

    monkeypatch.setattr("engine.anomaly.detection.IsolationForest", FakeIsolationForest)
    ts = list(range(30))
    vals = [1.0, 1.2, 0.9, 1.1, 1.0, 1.3] * 5
    anomalies = detect("iso_only_noise", ts, vals, sensitivity=3.0)
    assert anomalies == []


def test_density_cap_limits_anomalies_per_hour(monkeypatch):
    monkeypatch.setattr("config.settings.quality_max_anomaly_density_per_metric_per_hour", 1.0)
    anomalies = [
        MetricAnomaly(
            metric_name="m",
            timestamp=float(i * 600),
            value=float(i),
            change_type=ChangeType.spike,
            z_score=3.0 + i,
            mad_score=2.0 + i,
            isolation_score=-0.4,
            expected_range=(0.0, 1.0),
            severity=Severity.high,
            description="",
        )
        for i in range(6)
    ]
    # 0..3000 seconds ~= 0.83h -> cap should keep only one anomaly.
    kept = _apply_density_cap(anomalies, np.array([a.timestamp for a in anomalies], dtype=float))
    assert len(kept) == 1
