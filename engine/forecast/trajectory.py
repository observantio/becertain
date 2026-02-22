from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from engine.enums import Severity


@dataclass(frozen=True)
class TrajectoryForecast:
    metric_name: str
    current_value: float
    slope_per_second: float
    predicted_value_at_horizon: float
    time_to_threshold_seconds: Optional[float]
    breach_threshold: float
    confidence: float
    severity: Severity


def _linear_fit(ts: List[float], vals: List[float]) -> tuple[float, float]:
    t = np.array(ts, dtype=float)
    v = np.array(vals, dtype=float)
    t_norm = t - t[0]
    slope, intercept = np.polyfit(t_norm, v, 1)
    return float(slope), float(intercept)


def _r_squared(ts: List[float], vals: List[float], slope: float, intercept: float) -> float:
    t_norm = np.array(ts, dtype=float) - ts[0]
    v = np.array(vals, dtype=float)
    predicted = slope * t_norm + intercept
    ss_res = np.sum((v - predicted) ** 2)
    ss_tot = np.sum((v - np.mean(v)) ** 2)
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def forecast(
    metric_name: str,
    ts: List[float],
    vals: List[float],
    threshold: float,
    horizon_seconds: float = 1800.0,
) -> Optional[TrajectoryForecast]:
    if len(vals) < 8:
        return None

    slope, intercept = _linear_fit(ts, vals)
    r2 = _r_squared(ts, vals, slope, intercept)

    if r2 < 0.2 or slope == 0:
        return None

    now_offset = ts[-1] - ts[0]
    current = slope * now_offset + intercept
    predicted_at_horizon = slope * (now_offset + horizon_seconds) + intercept

    time_to_threshold: Optional[float] = None
    if slope > 0 and current < threshold:
        time_to_threshold = (threshold - current) / slope
    elif slope < 0 and current > threshold:
        time_to_threshold = (current - threshold) / abs(slope)

    will_breach = time_to_threshold is not None and time_to_threshold <= horizon_seconds
    if not will_breach and abs(predicted_at_horizon - threshold) / (abs(threshold) + 1e-9) > 0.5:
        return None

    confidence = round(min(0.99, r2 * (1.0 - min(1.0, abs(slope) / (abs(current) + 1e-9)))), 3)

    if time_to_threshold and time_to_threshold < 300:
        sev = Severity.critical
    elif time_to_threshold and time_to_threshold < 900:
        sev = Severity.high
    elif will_breach:
        sev = Severity.medium
    else:
        sev = Severity.low

    return TrajectoryForecast(
        metric_name=metric_name,
        current_value=round(current, 4),
        slope_per_second=round(slope, 6),
        predicted_value_at_horizon=round(predicted_at_horizon, 4),
        time_to_threshold_seconds=round(time_to_threshold, 1) if time_to_threshold else None,
        breach_threshold=threshold,
        confidence=confidence,
        severity=sev,
    )