"""
Error propagation detection for traces, identifying source services and affected downstream services.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from engine.enums import Severity
from engine.topology import DependencyGraph
from api.responses import ErrorPropagation
from config import settings


def detect_propagation(tempo_response: Dict[str, Any]) -> List[ErrorPropagation]:
    service_errors: Dict[str, int] = defaultdict(int)
    service_total: Dict[str, int] = defaultdict(int)
    graph = DependencyGraph()
    graph.from_spans(tempo_response)

    for trace in tempo_response.get("traces", []):
        service = trace.get("rootServiceName", "unknown")
        service_total[service] += 1
        has_error = False

        span_sets = []
        if isinstance(trace.get("spanSet"), dict):
            span_sets.append(trace.get("spanSet"))
        if isinstance(trace.get("spanSets"), list):
            span_sets.extend([s for s in trace.get("spanSets") if isinstance(s, dict)])
        for span_set in span_sets:
            for span in span_set.get("spans", []):
                attrs = {a.get("key", ""): a.get("value", {}) for a in span.get("attributes", [])}
                status_code = attrs.get("status.code", {}).get("stringValue", "").upper()
                if status_code in ("STATUS_CODE_ERROR", "ERROR"):
                    has_error = True
                    break
            if has_error:
                break

        if has_error:
            service_errors[service] += 1

    error_rates = {
        svc: service_errors[svc] / service_total[svc]
        for svc in service_total
        if service_total[svc] > 0
    }

    sources = [svc for svc, rate in error_rates.items() if rate >= settings.trace_error_rate_threshold]
    if not sources:
        return []

    results: List[ErrorPropagation] = []

    for source in sources:
        affected_services = sorted(graph.blast_radius(source).affected_downstream)
        if not affected_services:
            continue

        rate = error_rates[source]
        if rate >= settings.trace_error_severity_critical:
            severity = Severity.critical
        elif rate >= settings.trace_error_severity_high:
            severity = Severity.high
        else:
            severity = Severity.medium

        results.append(ErrorPropagation(
            source_service=source,
            affected_services=affected_services,
            error_rate=round(rate, 4),
            severity=severity,
        ))
    results.sort(key=lambda e: e.error_rate, reverse=True)
    return results
