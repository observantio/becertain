"""
Enumerations for severity levels, signal types, and change types used in the Be Certain Analysis Engine.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

    @classmethod
    def from_score(cls, score: float) -> "Severity":
        if score >= 0.75:
            return cls.critical
        if score >= 0.50:
            return cls.high
        if score >= 0.25:
            return cls.medium
        return cls.low

    def weight(self) -> int:
        return {"low": 1, "medium": 2, "high": 4, "critical": 8}[self.value]


class Signal(str, Enum):
    metrics = "metrics"
    logs = "logs"
    traces = "traces"
    events = "events"


class ChangeType(str, Enum):
    spike = "spike"
    drop = "drop"
    drift = "drift"
    shift = "shift"
    oscillation = "oscillation"


class RcaCategory(str, Enum):
    deployment = "deployment"
    resource_exhaustion = "resource_exhaustion"
    dependency_failure = "dependency_failure"
    traffic_surge = "traffic_surge"
    error_propagation = "error_propagation"
    slo_burn = "slo_burn"
    unknown = "unknown"
