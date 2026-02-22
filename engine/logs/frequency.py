from __future__ import annotations

from typing import Any, Dict, Iterator, List, Tuple

import numpy as np

from engine.enums import Severity
from api.responses import LogBurst

from config import settings

_BURST_RATIO_THRESHOLDS = [
    (thr, Severity(sev)) for thr, sev in settings.burst_ratio_thresholds
]


def _iter_entries(loki_response: Dict[str, Any]) -> Iterator[Tuple[float, str]]:
    for stream in loki_response.get("data", {}).get("result", []):
        for ts_ns, line in stream.get("values", []):
            yield float(ts_ns) / 1e9, line


def detect_bursts(loki_response: Dict[str, Any], window_seconds: float = 10.0) -> List[LogBurst]:
    entries = sorted(_iter_entries(loki_response), key=lambda x: x[0])
    if len(entries) < 2:
        return []

    timestamps = np.array([t for t, _ in entries])
    start, end = timestamps[0], timestamps[-1]
    total_duration = end - start
    if total_duration <= 0:
        return []

    baseline_rate = len(timestamps) / total_duration

    windows: List[Tuple[float, float, int]] = []
    i = 0
    while i < len(timestamps):
        w_start = timestamps[i]
        w_end = w_start + window_seconds
        count = int(np.searchsorted(timestamps, w_end, side="left")) - i
        windows.append((w_start, w_end, count))
        i += max(1, count)

    if not windows:
        return []

    bursts: List[LogBurst] = []
    for w_start, w_end, count in windows:
        rate = count / window_seconds
        ratio = rate / baseline_rate if baseline_rate > 0 else 0.0
        severity = next(
            (s for threshold, s in _BURST_RATIO_THRESHOLDS if ratio >= threshold),
            None,
        )
        if severity is None:
            continue
        bursts.append(LogBurst(
            window_start=w_start,
            window_end=w_end,
            rate_per_second=round(rate, 3),
            baseline_rate=round(baseline_rate, 3),
            ratio=round(ratio, 2),
            severity=severity,
        ))

    return bursts