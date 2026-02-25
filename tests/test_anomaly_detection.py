"""
Test cases for anomaly detection logic in the analysis engine, including output limiting and Granger causality series selection.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import pytest

from api.responses import MetricAnomaly
from engine.anomaly.detection import _mad_scores, _cusum_changepoints, _change_type, _severity, _compress_runs, detect
from engine.enums import ChangeType, Severity


def test_mad_and_cusum():
    arr = [1, 1, 1, 10, 1, 1, 1]
    import numpy as np
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
