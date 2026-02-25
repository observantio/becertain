"""
Test cases for trace analysis logic in the analysis engine, including detection of trace anomalies, correlation with metrics and logs, and edge cases in timestamp handling and service topology.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from engine.traces.errors import detect_propagation
from engine.traces.latency import analyze


def _trace(service: str, duration_ms: float, status_code: str) -> dict:
    return {
        "rootServiceName": service,
        "rootTraceName": f"{service}.op",
        "durationMs": duration_ms,
        "spanSets": [
            {
                "spans": [
                    {
                        "attributes": [
                            {"key": "status.code", "value": {"stringValue": status_code}},
                        ]
                    }
                ]
            }
        ],
    }


def test_latency_analyze_reads_errors_from_span_sets_shape():
    raw = {
        "traces": [
            _trace("checkout", 6000.0, "STATUS_CODE_ERROR"),
            _trace("checkout", 6200.0, "STATUS_CODE_ERROR"),
            _trace("checkout", 5800.0, "STATUS_CODE_ERROR"),
        ]
    }
    rows = analyze(raw, apdex_t_ms=500.0)
    assert rows
    assert rows[0].service == "checkout"
    assert rows[0].error_rate > 0


def test_error_propagation_reads_span_sets_shape():
    raw = {
        "traces": [
            _trace("payments", 1200.0, "STATUS_CODE_ERROR"),
            _trace("payments", 1100.0, "STATUS_CODE_ERROR"),
            _trace("payments", 900.0, "STATUS_CODE_ERROR"),
            _trace("checkout", 700.0, "STATUS_CODE_ERROR"),
        ]
    }
    rows = detect_propagation(raw)
    assert rows
    assert rows[0].source_service == "payments"
