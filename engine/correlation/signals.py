from __future__ import annotations

from dataclasses import dataclass
from typing import List

from api.responses import MetricAnomaly, LogBurst


@dataclass(frozen=True)
class LogMetricLink:
    metric_name: str
    metric_timestamp: float
    log_stream: str
    log_burst_start: float
    lag_seconds: float
    strength: float


def link_logs_to_metrics(
    metric_anomalies: List[MetricAnomaly],
    log_bursts: List[LogBurst],
    max_lag_seconds: float = 120.0,
) -> List[LogMetricLink]:
    links: List[LogMetricLink] = []

    for anomaly in metric_anomalies:
        for burst in log_bursts:
            lag = anomaly.timestamp - burst.start
            if 0 <= lag <= max_lag_seconds:
                strength = round(1.0 - (lag / max_lag_seconds), 3)
                links.append(LogMetricLink(
                    metric_name=anomaly.metric_name,
                    metric_timestamp=anomaly.timestamp,
                    log_stream=burst.stream,
                    log_burst_start=burst.start,
                    lag_seconds=round(lag, 1),
                    strength=strength,
                ))

    return sorted(links, key=lambda l: l.strength, reverse=True)