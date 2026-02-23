"""
Latency analysis for traces, including Apdex scoring and severity classification.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

from engine.enums import Severity
from api.responses import ServiceLatency
from config import settings

def _apdex(durations_ms: np.ndarray, t_ms: float) -> float:
    if durations_ms.size == 0:
        return 1.0
    satisfied = (durations_ms <= t_ms).sum()
    tolerating = ((durations_ms > t_ms) & (durations_ms <= 4 * t_ms)).sum()
    return round((satisfied + 0.5 * tolerating) / durations_ms.size, 4)

def _severity(p99: float, error_rate: float, apdex: float) -> Severity:
    score = 0.0
    if p99 >= settings.trace_latency_p99_critical:
        score += 0.5
    elif p99 >= settings.trace_latency_p99_high:
        score += 0.35
    elif p99 >= settings.trace_latency_p99_medium:
        score += 0.2

    if error_rate >= settings.trace_latency_error_critical:
        score += 0.4
    elif error_rate >= settings.trace_latency_error_high:
        score += 0.25
    elif error_rate >= settings.trace_latency_error_medium:
        score += 0.1

    if apdex < settings.trace_latency_apdex_poor:
        score += 0.1
    elif apdex < settings.trace_latency_apdex_marginal:
        score += 0.05

    return Severity.from_score(min(score, 1.0))


def analyze(tempo_response: Dict[str, Any], apdex_t_ms: float | None = None) -> List[ServiceLatency]:
    if apdex_t_ms is None:
        apdex_t_ms = settings.trace_latency_apdex_t_ms

    buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"durations": [], "errors": 0, "total": 0, "op": ""})

    for trace in tempo_response.get("traces", []):
        service = trace.get("rootServiceName", "unknown")
        operation = trace.get("rootTraceName", "unknown")
        duration_ms = float(trace.get("durationMs", 0))
        key = f"{service}::{operation}"

        bucket = buckets[key]
        bucket["durations"].append(duration_ms)
        bucket["total"] += 1
        bucket["op"] = operation

        for span in (trace.get("spanSet") or {}).get("spans", []):
            attrs = {a.get("key", ""): a.get("value", {}) for a in span.get("attributes", [])}
            status_code = attrs.get("status.code", {}).get("stringValue", "").upper()
            if status_code in ("STATUS_CODE_ERROR", "ERROR"):
                bucket["errors"] += 1
                break 

    results: List[ServiceLatency] = []

    for key, bucket in buckets.items():
        durations = np.array(bucket["durations"], dtype=float)
        if durations.size == 0:
            continue

        service = key.split("::")[0]
        p50, p95, p99 = np.percentile(durations, [50, 95, 99]).astype(float)
        error_rate = bucket["errors"] / bucket["total"]
        apdex_score = _apdex(durations, apdex_t_ms)
        sev = _severity(p99, error_rate, apdex_score)

        if sev == Severity.low:
            continue 

        results.append(ServiceLatency(
            service=service,
            operation=bucket["op"],
            p50_ms=round(p50, 2),
            p95_ms=round(p95, 2),
            p99_ms=round(p99, 2),
            apdex=apdex_score,
            error_rate=round(error_rate, 4),
            sample_count=bucket["total"],
            severity=sev,
        ))

    results.sort(key=lambda s: s.severity.weight(), reverse=True)
    return results