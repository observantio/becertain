from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Baseline:
    mean: float
    std: float
    lower: float
    upper: float
    seasonal_mean: Optional[float] = None
    sample_count: int = 0


def _hour_buckets(ts: List[float]) -> List[int]:
    return [(int(t) % 86400) // 3600 for t in ts]


def compute(ts: List[float], vals: List[float], z_threshold: float = 3.0) -> Baseline:
    arr = np.array(vals, dtype=float)
    n = len(arr)

    if n < 6:
        m = float(np.mean(arr))
        s = float(np.std(arr)) or 1.0
        return Baseline(mean=m, std=s, lower=m - z_threshold * s, upper=m + z_threshold * s, sample_count=n)

    seasonal_mean: Optional[float] = None

    if n >= 24:
        buckets = _hour_buckets(ts)
        bucket_map: Dict[int, List[float]] = {}
        for b, v in zip(buckets, vals):
            bucket_map.setdefault(b, []).append(v)
        hour_avgs = {h: float(np.mean(v)) for h, v in bucket_map.items()}
        detrended = np.array([v - hour_avgs.get(b, 0.0) for b, v in zip(buckets, vals)])
        m = float(np.mean(arr))
        s = float(np.std(detrended)) or 1.0
        seasonal_mean = float(np.mean(list(hour_avgs.values())))
    else:
        m = float(np.mean(arr))
        s = float(np.std(arr)) or 1.0

    return Baseline(
        mean=m,
        std=s,
        lower=m - z_threshold * s,
        upper=m + z_threshold * s,
        seasonal_mean=seasonal_mean,
        sample_count=n,
    )


def score(val: float, baseline: Baseline) -> Tuple[bool, float]:
    z = abs(val - baseline.mean) / baseline.std if baseline.std else 0.0
    return (val < baseline.lower or val > baseline.upper), round(z, 3)