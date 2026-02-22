from __future__ import annotations

from typing import List, Tuple

import numpy as np
from scipy.stats import linregress
from sklearn.ensemble import IsolationForest

from engine.enums import ChangeType, Severity
from api.responses import MetricAnomaly
from config import settings


def _mad_scores(arr: np.ndarray) -> np.ndarray:
    median = np.median(arr)
    mad = np.median(np.abs(arr - median))
    if mad == 0:
        return np.zeros_like(arr)
    return 0.6745 * (arr - median) / mad


from config import settings


def _cusum_changepoints(arr: np.ndarray, threshold: float | None = None) -> np.ndarray:
    if threshold is None:
        threshold = settings.cusum_threshold

    mu, sigma = arr.mean(), arr.std()
    if sigma == 0:
        return np.zeros(len(arr), dtype=bool)
    normed = (arr - mu) / sigma
    cusum_pos = np.zeros(len(arr))
    cusum_neg = np.zeros(len(arr))
    for i in range(1, len(arr)):
        cusum_pos[i] = max(0, cusum_pos[i-1] + normed[i] - 0.5)
        cusum_neg[i] = max(0, cusum_neg[i-1] - normed[i] - 0.5)
    return (cusum_pos > threshold) | (cusum_neg > threshold)


def _change_type(value: float, mean: float, z: float, trend_slope: float) -> ChangeType:
    if abs(trend_slope) > 0.1:
        return ChangeType.drift
    if z > 0:
        return ChangeType.spike
    if z < 0:
        return ChangeType.drop
    return ChangeType.shift


def _severity(z: float, mad: float, iso: int) -> Severity:
    score = 0.0
    az = abs(z)
    if az >= 4.0:   score += 0.5
    elif az >= 3.0: score += 0.35
    elif az >= 2.5: score += 0.2
    am = abs(mad)
    if am >= 5.0:   score += 0.35
    elif am >= 3.5: score += 0.25
    elif am >= 2.5: score += 0.15
    if iso == -1:   score += 0.15
    return Severity.from_score(min(score, 1.0))


def detect(
    metric: str,
    timestamps: List[float],
    values: List[float],
    sensitivity: float = 3.0,
) -> List[MetricAnomaly]:
    if len(values) < settings.min_samples:
        return []

    contamination = max(0.01, min(0.5, 0.5 / max(sensitivity, 0.1)))

    arr = np.array(values, dtype=float)
    ts = np.array(timestamps, dtype=float)
    finite = np.isfinite(arr)
    if finite.sum() < settings.min_samples:
        return []

    clean = arr[finite]
    mean, std = clean.mean(), clean.std()
    if std == 0:
        return []

    z_scores = (arr - mean) / std
    mad_scores = _mad_scores(arr)
    cusum_flags = _cusum_changepoints(arr)
    p5, p95 = float(np.percentile(clean, 5)), float(np.percentile(clean, 95))

    iso = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    iso_labels = iso.fit_predict(arr.reshape(-1, 1))
    iso_scores = iso.score_samples(arr.reshape(-1, 1))

    slope, *_ = linregress(np.arange(len(clean)), clean)

    anomalies: List[MetricAnomaly] = []
    for i, (t, v, z, m, c, iso_l, iso_s) in enumerate(
        zip(ts, arr, z_scores, mad_scores, cusum_flags, iso_labels, iso_scores)
    ):
        if not np.isfinite(v):
            continue
        flagged = (
            abs(z) >= settings.zscore_threshold
            or abs(m) >= settings.mad_threshold
            or iso_l == -1
            or c
        )
        if not flagged:
            continue

        sev = _severity(z, m, iso_l)
        ctype = _change_type(v, mean, z, slope)

        anomalies.append(MetricAnomaly(
            metric_name=metric,
            timestamp=float(t),
            value=float(v),
            change_type=ctype,
            z_score=round(float(z), 3),
            mad_score=round(float(m), 3),
            isolation_score=round(float(iso_s), 4),
            expected_range=(round(p5, 4), round(p95, 4)),
            severity=sev,
            description=(
                f"{metric}: {ctype.value} of {v:.4g} "
                f"(z={z:+.1f}, MAD={m:+.1f}, expected=[{p5:.4g}, {p95:.4g}])"
            ),
        ))

    return anomalies