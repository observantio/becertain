from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, List, TypeVar

from api.responses import MetricAnomaly

T = TypeVar("T")


@dataclass
class AnomalyGroup(Generic[T]):
    representative: T
    members: List[T] = field(default_factory=list)
    count: int = 1


def group_metric_anomalies(
    anomalies: List[MetricAnomaly],
    time_window: float = 120.0,
    by_metric: bool = True,
) -> List[AnomalyGroup[MetricAnomaly]]:
    if not anomalies:
        return []

    sorted_a = sorted(anomalies, key=lambda a: a.timestamp)
    groups: List[AnomalyGroup[MetricAnomaly]] = []
    current = AnomalyGroup(representative=sorted_a[0], members=[sorted_a[0]])

    for a in sorted_a[1:]:
        rep = current.representative
        same_metric = (not by_metric) or (a.metric_name == rep.metric_name)
        close_in_time = abs(a.timestamp - rep.timestamp) <= time_window

        if same_metric and close_in_time:
            current.members.append(a)
            current.count += 1
            if a.severity.weight() > rep.severity.weight():
                current.representative = a
        else:
            groups.append(current)
            current = AnomalyGroup(representative=a, members=[a])

    groups.append(current)
    return groups