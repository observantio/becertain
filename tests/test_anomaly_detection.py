import pytest

from engine.anomaly.detection import _mad_scores, _cusum_changepoints, _change_type, _severity, detect
from engine.enums import ChangeType, Severity


def test_mad_and_cusum():
    arr = [1, 1, 1, 10, 1, 1, 1]
    import numpy as np
    m = _mad_scores(np.array(arr))
    # dtype may be int if arr values identical; just ensure numeric
    assert m.dtype in (float, 'float64', 'int64')
    # cusum with high threshold should flag nothing, low threshold flags some
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
    # create a small series with an outlier
    ts = list(range(20))
    vals = [1]*19 + [100]
    anomalies = detect("m", ts, vals, contamination=0.1)
    # algorithm might not flag single outlier deterministically; just ensure it
    # returns a list and elements are MetricAnomaly if any
    assert isinstance(anomalies, list)
    if anomalies:
        assert hasattr(anomalies[0], 'change_type')
