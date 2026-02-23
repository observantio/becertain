"""
Temporal correlation logic to identify related anomalies across different signals (metrics, logs, traces) based on their occurrence within a configurable time window, and to compute a confidence score for the correlation based on the number and types of signals involved, to assist in root cause analysis and incident investigation.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set

from api.responses import MetricAnomaly, LogBurst, ServiceLatency


@dataclass
class CorrelatedEvent:
    window_start: float
    window_end: float
    metric_anomalies: List[MetricAnomaly] = field(default_factory=list)
    log_bursts: List[LogBurst] = field(default_factory=list)
    service_latency: List[ServiceLatency] = field(default_factory=list)
    signal_count: int = 0
    confidence: float = 0.0


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return a_start <= b_end and b_start <= a_end


from config import settings

def correlate(
    metric_anomalies: List[MetricAnomaly],
    log_bursts: List[LogBurst],
    service_latency: List[ServiceLatency],
    window_seconds: float | None = None,
) -> List[CorrelatedEvent]:
    if window_seconds is None:
        window_seconds = settings.correlation_window_seconds

    anchor_times: List[float] = sorted(
        [a.timestamp for a in metric_anomalies]
        + [getattr(b, "start", getattr(b, "window_start", None)) for b in log_bursts]
    )

    if not anchor_times:
        return []

    events: List[CorrelatedEvent] = []
    used: Set[float] = set()

    for anchor in anchor_times:
        if anchor in used:
            continue

        w_start = anchor - window_seconds
        w_end = anchor + window_seconds

        ma = [a for a in metric_anomalies if w_start <= a.timestamp <= w_end]
        lb = [
            b for b in log_bursts
            if _overlap(
                w_start,
                w_end,
                getattr(b, "start", getattr(b, "window_start", None)),
                getattr(b, "end", getattr(b, "window_end", None)),
            )
        ]
        sl = list(service_latency) if (ma or lb) else []

        sig = len(ma) + len(lb) + len(sl)
        if sig < 2:
            continue

        metric_score = min(settings.correlation_score_max, len(ma) * settings.correlation_weight_time)
        log_score = min(settings.correlation_score_max, len(lb) * settings.correlation_weight_latency)
        trace_score = min(settings.correlation_errors_cap, len(sl) * settings.correlation_weight_errors)
        confidence = round(min(settings.correlation_score_max, metric_score + log_score + trace_score), 3)

        events.append(CorrelatedEvent(
            window_start=w_start,
            window_end=w_end,
            metric_anomalies=ma,
            log_bursts=lb,
            service_latency=sl,
            signal_count=sig,
            confidence=confidence,
        ))

        for a in anchor_times:
            if w_start <= a <= w_end:
                used.add(a)

    return sorted(events, key=lambda e: e.confidence, reverse=True)