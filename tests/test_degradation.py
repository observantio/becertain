import pytest

from engine.forecast.degradation import _ema, _acceleration, analyze
from engine.enums import Severity


def test_ema_and_acceleration():
    vals = [1, 2, 3, 4, 5]
    ema = _ema(vals, alpha=0.5)
    assert len(ema) == len(vals)
    acc = _acceleration(ema)
    assert isinstance(acc, float)


def test_analyze_none_short():
    assert analyze("m", [0, 1, 2], [1, 2, 3]) is None


def test_analyze_degrading():
    ts = list(range(20))
    vals = [i * 2 for i in ts]
    sig = analyze("m", ts, vals)
    assert isinstance(sig, object)
    assert sig.trend == "degrading"
    assert sig.severity in Severity
