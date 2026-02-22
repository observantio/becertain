from __future__ import annotations

from dataclasses import dataclass
from typing import List

from engine.enums import Severity


@dataclass(frozen=True)
class SloBurnAlert:
    service: str
    window_label: str
    error_rate: float
    burn_rate: float
    budget_consumed_pct: float
    severity: Severity


_WINDOWS = [
    ("1h",  3600,   14.4, Severity.critical),
    ("6h",  21600,  6.0,  Severity.high),
    ("1d",  86400,  3.0,  Severity.medium),
    ("3d",  259200, 1.0,  Severity.low),
]

_MONTH_SECONDS = 30 * 86400


def evaluate(
    service: str,
    error_counts: List[float],
    total_counts: List[float],
    ts: List[float],
    target_availability: float = 0.999,
) -> List[SloBurnAlert]:
    if not error_counts or not total_counts or len(ts) < 2:
        return []

    duration = ts[-1] - ts[0]
    total = sum(total_counts)
    errors = sum(error_counts)

    if total == 0:
        return []

    error_rate = errors / total
    allowed_error_rate = 1.0 - target_availability
    if allowed_error_rate <= 0:
        return []

    burn_rate = error_rate / allowed_error_rate
    alerts: List[SloBurnAlert] = []

    for label, window_s, threshold, sev in _WINDOWS:
        if duration < window_s * 0.5:
            continue
        if burn_rate >= threshold:
            consumed = min(100.0, (burn_rate * duration) / _MONTH_SECONDS * 100)
            alerts.append(SloBurnAlert(
                service=service,
                window_label=label,
                error_rate=round(error_rate, 6),
                burn_rate=round(burn_rate, 3),
                budget_consumed_pct=round(consumed, 2),
                severity=sev,
            ))
            break

    return alerts