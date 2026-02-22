from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from api.responses import MetricAnomaly


@dataclass
class AnomalyCluster:
    cluster_id: int
    members: List[MetricAnomaly]
    centroid_timestamp: float
    centroid_value: float
    metric_names: List[str]
    size: int
    is_noise: bool = False


def _feature_matrix(anomalies: List[MetricAnomaly]) -> np.ndarray:
    ts_arr = np.array([a.timestamp for a in anomalies], dtype=float)
    val_arr = np.array([a.value for a in anomalies], dtype=float)
    ts_norm = (ts_arr - ts_arr.min()) / (np.ptp(ts_arr) + 1e-9)
    val_norm = (val_arr - val_arr.min()) / (np.ptp(val_arr) + 1e-9)
    return np.column_stack([ts_norm, val_norm])


def cluster(
    anomalies: List[MetricAnomaly],
    eps: float = 0.1,
    min_samples: int = 2,
) -> List[AnomalyCluster]:
    if len(anomalies) < min_samples:
        return []

    try:
        from sklearn.cluster import DBSCAN
    except ImportError:
        return _fallback_cluster(anomalies)

    X = _feature_matrix(anomalies)
    labels = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean").fit_predict(X)

    clusters: dict[int, List[MetricAnomaly]] = {}
    for label, anomaly in zip(labels, anomalies):
        clusters.setdefault(int(label), []).append(anomaly)

    result: List[AnomalyCluster] = []
    for cid, members in clusters.items():
        result.append(AnomalyCluster(
            cluster_id=cid,
            members=members,
            centroid_timestamp=float(np.mean([a.timestamp for a in members])),
            centroid_value=float(np.mean([a.value for a in members])),
            metric_names=list(dict.fromkeys(a.metric_name for a in members)),
            size=len(members),
            is_noise=cid == -1,
        ))

    return sorted(result, key=lambda c: c.size, reverse=True)


def _fallback_cluster(anomalies: List[MetricAnomaly]) -> List[AnomalyCluster]:
    if not anomalies:
        return []
    return [AnomalyCluster(
        cluster_id=0,
        members=anomalies,
        centroid_timestamp=float(np.mean([a.timestamp for a in anomalies])),
        centroid_value=float(np.mean([a.value for a in anomalies])),
        metric_names=list(dict.fromkeys(a.metric_name for a in anomalies)),
        size=len(anomalies),
    )]