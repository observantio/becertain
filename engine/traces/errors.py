from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from engine.enums import Severity
from api.responses import ErrorPropagation


def detect_propagation(tempo_response: Dict[str, Any]) -> List[ErrorPropagation]:
    """
    Identify services that have errors and which downstream services
    experience elevated error rates within the same time window.
    Uses error co-occurrence across root service names as a propagation proxy.
    """
    service_errors: Dict[str, int] = defaultdict(int)
    service_total: Dict[str, int] = defaultdict(int)
    errored_traces: List[str] = []

    for trace in tempo_response.get("traces", []):
        service = trace.get("rootServiceName", "unknown")
        service_total[service] += 1
        has_error = False
        for span in (trace.get("spanSet") or {}).get("spans", []):
            attrs = {a["key"]: a.get("value", {}) for a in span.get("attributes", [])}
            if attrs.get("status.code", {}).get("stringValue", "") in ("STATUS_CODE_ERROR", "ERROR"):
                has_error = True
        if has_error:
            service_errors[service] += 1
            errored_traces.append(service)

    error_rates = {
        s: service_errors[s] / service_total[s]
        for s in service_total
        if service_total[s] > 0
    }

    sources = [s for s, r in error_rates.items() if r >= 0.05]
    if not sources:
        return []

    all_erroring = set(s for s, r in error_rates.items() if r > 0)
    results: List[ErrorPropagation] = []

    for source in sources:
        affected = sorted(all_erroring - {source})
        if not affected:
            continue
        rate = error_rates[source]
        sev = Severity.critical if rate >= 0.25 else Severity.high if rate >= 0.10 else Severity.medium
        results.append(ErrorPropagation(
            source_service=source,
            affected_services=affected,
            error_rate=round(rate, 4),
            severity=sev,
        ))

    results.sort(key=lambda e: e.error_rate, reverse=True)
    return results