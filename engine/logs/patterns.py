from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterator, List, Tuple

from engine.enums import Severity
from api.responses import LogPattern

_NOISE = re.compile(
    r"\b(?:"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"  
    r"|\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"  
    r"|(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?"        
    r"|\d+\.?\d*(?:ms|s|m|h|us|ns)\b"            
    r"|0x[0-9a-f]+"                               
    r"|\b\d{4,}\b"                                
    r")\b",
    re.I,
)

_SEVERITY_RE = {
    Severity.critical: re.compile(r"\b(fatal|panic|oom|killed|segfault|out of memory)\b", re.I),
    Severity.high:     re.compile(r"\b(error|err|exception|failed|failure|crash|timeout|unavailable|refused)\b", re.I),
    Severity.medium:   re.compile(r"\b(warn|warning|slow|retry|retrying|degraded|circuit)\b", re.I),
}


def _iter_entries(loki_response: Dict[str, Any]) -> Iterator[Tuple[float, str]]:
    for stream in loki_response.get("data", {}).get("result", []):
        for ts_ns, line in stream.get("values", []):
            yield float(ts_ns) / 1e9, line


def _normalize(line: str) -> str:
    return re.sub(r"\s+", " ", _NOISE.sub("<_>", line)).strip()[:180]


def _classify(line: str) -> Severity:
    for severity in (Severity.critical, Severity.high, Severity.medium):
        if _SEVERITY_RE[severity].search(line):
            return severity
    return Severity.low


def _entropy(tokens: List[str]) -> float:
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    total = len(tokens)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def analyze(loki_response: Dict[str, Any]) -> List[LogPattern]:
    buckets: Dict[str, Dict] = defaultdict(lambda: {
        "count": 0,
        "first": float("inf"),
        "last": float("-inf"),
        "severity": Severity.low,
        "sample": "",
        "tokens": [],
    })

    for ts, line in _iter_entries(loki_response):
        key = _normalize(line)
        b = buckets[key]
        b["count"] += 1
        b["first"] = min(b["first"], ts)
        b["last"] = max(b["last"], ts)
        if not b["sample"]:
            b["sample"] = line[:300]
        sev = _classify(line)
        if sev.weight() > b["severity"].weight():
            b["severity"] = sev
        if len(b["tokens"]) < 500:
            b["tokens"].extend(key.split())

    results: List[LogPattern] = []
    for pattern, b in buckets.items():
        if b["first"] == float("inf"):
            continue
        duration = max(b["last"] - b["first"], 1.0)
        results.append(LogPattern(
            pattern=pattern,
            count=b["count"],
            first_seen=b["first"],
            last_seen=b["last"],
            rate_per_minute=round(b["count"] / (duration / 60), 4),
            entropy=round(_entropy(b["tokens"]), 4),
            severity=b["severity"],
            sample=b["sample"],
        ))

    results.sort(key=lambda p: (p.severity.weight(), p.count), reverse=True)
    return results[:100]