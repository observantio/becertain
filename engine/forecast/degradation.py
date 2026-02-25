"""
Degradation analysis logic for time series metrics, including trend detection, volatility measurement, and severity classification based on configured thresholds, to identify potential performance degradations in monitored systems.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from engine.enums import Severity
from config import settings


@dataclass(frozen=True)
class DegradationSignal:
    metric_name: str
    degradation_rate: float
    volatility: float
    trend: str
    window_seconds: float
    severity: Severity
    is_accelerating: bool


def _ema(vals: List[float], alpha: float | None = None) -> np.ndarray:
    if alpha is None:
        alpha = settings.forecast_ema_alpha
    result = np.zeros(len(vals))
    result[0] = vals[0]
    for i in range(1, len(vals)):
        result[i] = alpha * vals[i] + (1 - alpha) * result[i - 1]
    return result


def _acceleration(vals: np.ndarray) -> float:
    if len(vals) < 4:
        return 0.0
    first_half = np.mean(np.diff(vals[: len(vals) // 2]))
    second_half = np.mean(np.diff(vals[len(vals) // 2 :]))
    return float(second_half - first_half)


def analyze(
    metric_name: str,
    ts: List[float],
    vals: List[float],
    min_degradation_rate: float | None = None,
) -> Optional[DegradationSignal]:
    if min_degradation_rate is None:
        min_degradation_rate = settings.forecast_min_degradation_rate
    if len(vals) < settings.forecast_degradation_min_length:
        return None

    arr = np.array(vals, dtype=float)
    smoothed = _ema(list(arr))
    window = ts[-1] - ts[0]

    overall_slope = float(np.polyfit(np.linspace(0, 1, len(smoothed)), smoothed, 1)[0])
    volatility = float(np.std(arr) / (np.mean(np.abs(arr)) + 1e-9))
    acceleration = _acceleration(smoothed)

    rate = abs(overall_slope) / (np.mean(np.abs(arr)) + 1e-9)
    if rate < min_degradation_rate:
        return None

    trend = "degrading" if overall_slope > 0 else "recovering"

    if rate > settings.forecast_degradation_threshold_critical or (
        rate > settings.forecast_degradation_threshold_high and acceleration > 0
    ):
        sev = Severity.critical
    elif rate > settings.forecast_degradation_threshold_high:
        sev = Severity.high
    elif rate > settings.forecast_degradation_threshold_medium:
        sev = Severity.medium
    else:
        sev = Severity.low

    return DegradationSignal(
        metric_name=metric_name,
        degradation_rate=round(rate, 4),
        volatility=round(volatility, 4),
        trend=trend,
        window_seconds=round(window, 1),
        severity=sev,
        is_accelerating=acceleration > 0 and overall_slope > 0,
    )
