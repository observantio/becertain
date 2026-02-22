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


def correlate(
    metric_anomalies: List[MetricAnomaly],
    log_bursts: List[LogBurst],
    service_latency: List[ServiceLatency],
    window_seconds: float = 60.0,
) -> List[CorrelatedEvent]:
    # log bursts may use either 'start'/'end' or newer 'window_start'/'window_end'
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

        metric_score = min(1.0, len(ma) * 0.25)
        log_score = min(1.0, len(lb) * 0.35)
        trace_score = min(0.35, len(sl) * 0.1)
        confidence = round(min(1.0, metric_score + log_score + trace_score), 3)

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