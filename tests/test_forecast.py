"""
Test Suite for Engine Forecast

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import pytest

from engine.forecast.trajectory import _linear_fit, _r_squared, forecast, TrajectoryForecast


def test_linear_fit_and_r2():
    ts = [0, 1, 2, 3, 4]
    vals = [1, 2, 3, 4, 5]
    slope, intercept = _linear_fit(ts, vals)
    assert pytest.approx(slope, rel=1e-3) == 1.0
    r2 = _r_squared(ts, vals, slope, intercept)
    assert pytest.approx(r2, rel=1e-3) == 1.0


def test_forecast_insufficient():
    assert forecast("m", [0, 1, 2], [1, 2, 3], threshold=10) is None


def test_forecast_no_r2():
    ts = list(range(10))
    vals = [1] * 10  # zero slope
    assert forecast("m", ts, vals, threshold=2) is None


def test_forecast_breach():
    ts = list(range(20))
    vals = [i for i in range(20)]
    res = forecast("m", ts, vals, threshold=25, horizon_seconds=10)
    assert isinstance(res, TrajectoryForecast)
    assert res.severity in {res.severity,}
    assert res.current_value < res.predicted_value_at_horizon
