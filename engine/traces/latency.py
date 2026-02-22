from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

from engine.enums import Severity
from api.responses import ServiceLatency

_APDEX_POOR = 0.7


def _apdex(durations_ms: np.ndarray, t_ms: float) -> float:
    """Apdex score: satisfied (<T), tolerating (<4T), frustrated (>=4T)."""
    satisfied = (durations_ms <= t_ms).sum()
    tolerating = ((durations_ms > t_ms) & (durations_ms <= 4 * t_ms)).sum()
    total = len(durations_ms)
    if total == 0:
        return 1.0
    return round((satisfied + tolerating * 0.5) / total, 4)


def _severity(p99: float, error_rate: float, apdex: float) -> Severity:
    score = 0.0
    if p99 >= 5000:   score += 0.5
    elif p99 >= 2000: score += 0.35
    elif p99 >= 500:  score += 0.2
    if error_rate >= 0.25: score += 0.4
    elif error_rate >= 0.10: score += 0.25
    elif error_rate >= 0.02: score += 0.1
    if apdex < 0.5:  score += 0.1
    elif apdex < 0.7: score += 0.05
    return Severity.from_score(min(score, 1.0))


def analyze(tempo_response: Dict[str, Any], apdex_t_ms: float = 500.0) -> List[ServiceLatency]:
    buckets: Dict[str, Dict] = defaultdict(lambda: {"durations": [], "errors": 0, "total": 0, "op": ""})

    for trace in tempo_response.get("traces", []):
        service = trace.get("rootServiceName", "unknown")
        op = trace.get("rootTraceName", "unknown")
        duration_ms = float(trace.get("durationMs", 0))
        key = f"{service}::{op}"
        b = buckets[key]
        b["durations"].append(duration_ms)
        b["total"] += 1
        b["op"] = op
        for span in (trace.get("spanSet") or {}).get("spans", []):
            attrs = {a["key"]: a.get("value", {}) for a in span.get("attributes", [])}
            if attrs.get("status.code", {}).get("stringValue", "") in ("STATUS_CODE_ERROR", "ERROR"):
                b["errors"] += 1

    results: List[ServiceLatency] = []
    for key, b in buckets.items():
        if not b["durations"]:
            continue
        service = key.split("::")[0]
        arr = np.array(b["durations"])
        p50, p95, p99 = float(np.percentile(arr, 50)), float(np.percentile(arr, 95)), float(np.percentile(arr, 99))
        error_rate = b["errors"] / b["total"]
        apdex = _apdex(arr, apdex_t_ms)
        sev = _severity(p99, error_rate, apdex)
        if sev == Severity.low:
            continue
        results.append(ServiceLatency(
            service=service,
            operation=b["op"],
            p50_ms=round(p50, 2),
            p95_ms=round(p95, 2),
            p99_ms=round(p99, 2),
            apdex=apdex,
            error_rate=round(error_rate, 4),
            sample_count=b["total"],
            severity=sev,
        ))

    results.sort(key=lambda s: s.severity.weight(), reverse=True)
    return results