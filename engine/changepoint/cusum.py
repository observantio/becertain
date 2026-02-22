from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from engine.enums import ChangeType


@dataclass(frozen=True)
class ChangePoint:
    index: int
    timestamp: float
    value_before: float
    value_after: float
    magnitude: float
    change_type: ChangeType


def _classify(before: float, after: float, std: float) -> ChangeType:
    delta = after - before
    relative = abs(delta) / (abs(before) + 1e-9)
    if relative > 0.5:
        return ChangeType.spike if delta > 0 else ChangeType.drop
    if abs(delta) > 2 * std:
        return ChangeType.shift
    return ChangeType.drift


def _detect_oscillation(arr: np.ndarray, window: int = 10) -> List[int]:
    sign_changes = np.diff(np.sign(np.diff(arr)))
    indices = np.where(np.abs(sign_changes) > 1)[0]
    if len(indices) < window // 2:
        return []
    density = len(indices) / len(arr)
    return list(indices) if density > 0.3 else []


def detect(ts: List[float], vals: List[float], threshold_sigma: float = 4.0) -> List[ChangePoint]:
    if len(vals) < 10:
        return []

    arr = np.array(vals, dtype=float)
    mu = np.mean(arr)
    sigma = np.std(arr)
    if sigma == 0:
        return []

    oscillation_indices = set(_detect_oscillation(arr))

    k = 0.5 * sigma
    h = threshold_sigma * sigma
    cusum_pos = cusum_neg = 0.0
    results: List[ChangePoint] = []

    for i in range(1, len(arr)):
        cusum_pos = max(0.0, cusum_pos + arr[i] - mu - k)
        cusum_neg = max(0.0, cusum_neg - arr[i] + mu - k)

        if cusum_pos > h or cusum_neg > h:
            before = float(np.mean(arr[max(0, i - 5):i]))
            after = float(np.mean(arr[i:min(len(arr), i + 5)]))
            ctype = ChangeType.oscillation if i in oscillation_indices else _classify(before, after, sigma)
            results.append(ChangePoint(
                index=i,
                timestamp=ts[i],
                value_before=round(before, 4),
                value_after=round(after, 4),
                magnitude=round(abs(after - before) / sigma, 3),
                change_type=ctype,
            ))
            cusum_pos = cusum_neg = 0.0

    return results