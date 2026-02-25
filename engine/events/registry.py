"""
Registry for deployment events, allowing for recording and querying of deployment-related information such as service name, timestamp, version, author, environment, source, and additional metadata, to facilitate correlation with observed anomalies and support root cause analysis.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""


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

    def near_timestamp(self, ts: float, window_seconds: float | None = None) -> List[DeploymentEvent]:
        from config import settings
        if window_seconds is None:
            window_seconds = settings.events_window_seconds
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
