from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from engine.enums import Severity


@dataclass(frozen=True)
class DegradationSignal:
    metric_name: str
    degradation_rate: float
    volatility: float
    trend: str
    window_seconds: float
    severity: Severity
    is_accelerating: bool


def _ema(vals: List[float], alpha: float = 0.3) -> np.ndarray:
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
    min_degradation_rate: float = 0.01,
) -> Optional[DegradationSignal]:
    if len(vals) < 10:
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

    if rate > 0.3 or (rate > 0.1 and acceleration > 0):
        sev = Severity.critical
    elif rate > 0.15:
        sev = Severity.high
    elif rate > 0.05:
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