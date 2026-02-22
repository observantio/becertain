from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DeploymentEvent:
    service: str
    timestamp: float
    version: str
    author: str = ""
    environment: str = "production"
    source: str = "unknown"
    metadata: Dict[str, str] = field(default_factory=dict)


class EventRegistry:
    def __init__(self) -> None:
        self._events: List[DeploymentEvent] = []

    def register(self, event: DeploymentEvent) -> None:
        self._events.append(event)

    def register_many(self, events: List[DeploymentEvent]) -> None:
        self._events.extend(events)

    def in_window(self, start: float, end: float) -> List[DeploymentEvent]:
        return [e for e in self._events if start <= e.timestamp <= end]

    def near_timestamp(self, ts: float, window_seconds: float = 300.0) -> List[DeploymentEvent]:
        return self.in_window(ts - window_seconds, ts + window_seconds)

    def for_service(self, service: str) -> List[DeploymentEvent]:
        return [e for e in self._events if e.service == service]

    def most_recent(self, service: str) -> Optional[DeploymentEvent]:
        svc_events = self.for_service(service)
        return max(svc_events, key=lambda e: e.timestamp) if svc_events else None

    def list_all(self) -> List[DeploymentEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()