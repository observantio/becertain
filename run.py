#!/usr/bin/env python3

"""
Regression and integration test runner for Be Certain API.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict

import httpx
import jwt

BASE_URL = "http://localhost:4322/api/v1"
TENANT = "Av45ZchZsQdKjN8XyG"
NOW = int(time.time())
H1 = NOW - 3600
H24 = NOW - 86400
HEADERS = {"Content-Type": "application/json"}
SERVICE_TOKEN = os.getenv("BECERTAIN_EXPECTED_SERVICE_TOKEN", "replace_with_strong_token")
VERIFY_KEY = os.getenv("BECERTAIN_CONTEXT_VERIFY_KEY", "replace_with_strong_key")
ISSUER = os.getenv("BECERTAIN_CONTEXT_ISSUER", "beobservant-main")
AUDIENCE = os.getenv("BECERTAIN_CONTEXT_AUDIENCE", "becertain")


def _context_jwt() -> str:
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 600,
        "tenant_id": TENANT,
        "org_id": TENANT,
        "user_id": "local-runner",
        "username": "local-runner",
        "permissions": ["read:rca", "create:rca"],
        "group_ids": [],
        "role": "admin",
        "is_superuser": True,
    }
    return jwt.encode(payload, VERIFY_KEY, algorithm="HS256")


HEADERS.update({
    "X-Service-Token": SERVICE_TOKEN,
    "Authorization": f"Bearer {_context_jwt()}",
})


@dataclass(frozen=True)
class Case:
    label: str
    method: str
    path: str
    body: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    expect: int = 200
    section: str = ""


def base(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    d: Dict[str, Any] = {"tenant_id": TENANT, "start": H1, "end": NOW}
    if extra:
        d.update(extra)
    return d


CASES: list[Case] = [
    # ── Events Setup ──────────────────────────────────────
    Case("POST deployment event", "POST", "/events/deployment", section="Events Setup", body={
        "tenant_id": TENANT, "service": "payment-service", "version": "v2.1.0",
        "timestamp": NOW - 1800, "deployed_by": "ci-bot", "environment": "production",
    }),
    Case("GET deployments", "GET", "/events/deployments", section="Events Setup",
         params={"tenant_id": TENANT}),

    # ── Full RCA ──────────────────────────────────────────
    Case("single service", "POST", "/analyze", section="Full RCA",
         body=base({"services": ["payment-service"]})),
    Case("multi service", "POST", "/analyze", section="Full RCA",
         body=base({"services": ["payment-service", "order-service"], "sensitivity": 2.5})),
    Case("no services (global)", "POST", "/analyze", section="Full RCA", body=base()),
    Case("custom metric queries", "POST", "/analyze", section="Full RCA",
         body=base({"metric_queries": ["sum(traces_spanmetrics_calls_total) by (service)"]})),
    Case("custom log query", "POST", "/analyze", section="Full RCA",
         body=base({"log_query": '{app="payment-service"} |= "error"'})),
    Case("high sensitivity", "POST", "/analyze", section="Full RCA",
         body=base({"sensitivity": 1.5})),
    Case("low sensitivity", "POST", "/analyze", section="Full RCA",
         body=base({"sensitivity": 5.0})),
    Case("wider correlation window", "POST", "/analyze", section="Full RCA",
         body=base({"correlation_window": 600})),
    Case("24h window", "POST", "/analyze", section="Full RCA",
         body={**base(), "start": H24}),

    # ── Metrics ───────────────────────────────────────────
    Case("request rate", "POST", "/anomalies/metrics", section="Metrics",
         body=base({"query": "sum(rate(traces_spanmetrics_calls_total[5m])) by (service)"})),
    Case("p99 latency", "POST", "/anomalies/metrics", section="Metrics",
         body=base({"query": "histogram_quantile(0.99, sum(rate(traces_spanmetrics_latency_bucket[5m])) by (le, service))"})),
    Case("error rate", "POST", "/anomalies/metrics", section="Metrics",
         body=base({"query": 'sum(rate(traces_spanmetrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m])) by (service)'})),
    Case("memory", "POST", "/anomalies/metrics", section="Metrics",
         body=base({"query": "system_memory_usage_bytes"})),
    Case("CPU", "POST", "/anomalies/metrics", section="Metrics",
         body=base({"query": "sum(rate(system_cpu_time_seconds_total[5m])) by (cpu)"})),
    Case("changepoints memory", "POST", "/changepoints", section="Metrics",
         body=base({"query": "system_memory_usage_bytes"})),
    Case("changepoints request rate", "POST", "/changepoints", section="Metrics",
         body=base({"query": "sum(rate(traces_spanmetrics_calls_total[5m])) by (service)"})),

    # ── Logs ──────────────────────────────────────────────
    Case("patterns service", "POST", "/anomalies/logs/patterns", section="Logs",
         body=base({"query": '{service="payment-service"}'})),
    Case("patterns error level", "POST", "/anomalies/logs/patterns", section="Logs",
         body=base({"query": '{level="error"}'})),
    Case("patterns global", "POST", "/anomalies/logs/patterns", section="Logs",
         body=base({"query": '{job=~".+"}'})),
    Case("bursts service", "POST", "/anomalies/logs/bursts", section="Logs",
         body=base({"query": '{service="payment-service"}'})),
    Case("bursts global", "POST", "/anomalies/logs/bursts", section="Logs",
         body=base({"query": '{job=~".+"}'})),

    # ── Traces ────────────────────────────────────────────
    Case("service filter", "POST", "/anomalies/traces", section="Traces",
         body=base({"services": ["web-frontend"], "apdex_threshold": 0.7})),
    Case("strict apdex", "POST", "/anomalies/traces", section="Traces",
         body=base({"apdex_threshold": 0.95})),
    Case("no service filter", "POST", "/anomalies/traces", section="Traces", body=base()),

    # ── Correlation ───────────────────────────────────────
    Case("service scoped", "POST", "/correlate", section="Correlation",
         body=base({"services": ["payment-service"]})),
    Case("wide window", "POST", "/correlate", section="Correlation",
         body=base({"correlation_window": 600})),
    Case("custom log query", "POST", "/correlate", section="Correlation",
         body=base({"log_query": '{app="payment-service"}'})),

    # ── SLO ───────────────────────────────────────────────
    Case("99.9% target", "POST", "/slo/burn", section="SLO",
         body=base({"service": "payment-service", "target_availability": 0.999})),
    Case("99.5% target", "POST", "/slo/burn", section="SLO",
         body=base({"service": "payment-service", "target_availability": 0.995})),

    Case("custom queries", "POST", "/slo/burn", section="SLO",
         body=base({"service": "payment-service", "target_availability": 0.999,
                    "error_query": "sum(rate(traces_spanmetrics_calls_total[5m]))",
                    "total_query": "sum(rate(traces_spanmetrics_calls_total[5m]))"})),
    Case("24h window SLO", "POST", "/slo/burn", section="SLO",
         body={**base(), "start": H24, "service": "payment-service", "target_availability": 0.999}),

    # ── Topology ──────────────────────────────────────────
    Case("depth 5", "POST", "/topology/blast-radius", section="Topology",
         body={**base(), "root_service": "payment-service", "depth": 5}),
    Case("depth 1", "POST", "/topology/blast-radius", section="Topology",
         body={**base(), "root_service": "payment-service", "depth": 1}),
    Case("order service", "POST", "/topology/blast-radius", section="Topology",
         body={**base(), "root_service": "order-service", "depth": 3}),

    # ── Forecast ─────────────────────────────────────────
    Case("default queries", "POST", "/forecast/trajectory", section="Forecast", body=base()),
    Case("24h window", "POST", "/forecast/trajectory", section="Forecast",
         body={**base(), "start": H24}),
    Case("service scoped", "POST", "/forecast/trajectory", section="Forecast",
         body=base({"services": ["payment-service"]})),

    # ── Causal ────────────────────────────────────────────
    Case("granger cold", "POST", "/causal/granger", section="Causal", body=base()),
    Case("granger warm", "POST", "/causal/granger", section="Causal", body=base()),
    Case("granger custom metrics", "POST", "/causal/granger", section="Causal",
         body=base({"metric_queries": ["sum(traces_spanmetrics_calls_total) by (service)"]})),
    Case("bayesian with services", "POST", "/causal/bayesian", section="Causal",
         body=base({"services": ["payment-service", "order-service"]})),
    Case("bayesian no services", "POST", "/causal/bayesian", section="Causal", body=base()),

    # ── ML Weights ────────────────────────────────────────
    Case("weights acme", "GET", "/ml/weights", section="ML Weights",
         params={"tenant_id": "acme"}),
    Case("weights other-tenant", "GET", "/ml/weights", section="ML Weights",
         params={"tenant_id": "other-tenant"}),
    Case("feedback metrics correct", "POST", "/ml/weights/feedback", section="ML Weights",
         params={"tenant_id": "acme", "signal": "metrics", "was_correct": "true"}),
    Case("feedback logs correct", "POST", "/ml/weights/feedback", section="ML Weights",
         params={"tenant_id": "acme", "signal": "logs", "was_correct": "true"}),
    Case("feedback traces incorrect", "POST", "/ml/weights/feedback", section="ML Weights",
         params={"tenant_id": "acme", "signal": "traces", "was_correct": "false"}),
    Case("weights after feedback", "GET", "/ml/weights", section="ML Weights",
         params={"tenant_id": "acme"}),
    Case("feedback invalid signal", "POST", "/ml/weights/feedback", section="ML Weights",
         params={"tenant_id": "acme", "signal": "invalid_signal", "was_correct": "true"}, expect=400),
    # FIX: reset takes query param tenant_id, not body
    Case("weights reset", "POST", "/ml/weights/reset", section="ML Weights",
         params={"tenant_id": "acme"}),
    Case("weights after reset", "GET", "/ml/weights", section="ML Weights",
         params={"tenant_id": "acme"}),

    # ── Multi-tenancy ─────────────────────────────────────
    Case("tenant isolation check", "GET", "/ml/weights", section="Multi-tenancy",
         params={"tenant_id": "other-tenant"}),

    # ── Events Cleanup ────────────────────────────────────
    Case("DELETE deployments", "DELETE", "/events/deployments", section="Events Cleanup",
         params={"tenant_id": TENANT}),
    Case("GET deployments empty", "GET", "/events/deployments", section="Events Cleanup",
         params={"tenant_id": TENANT}),

    # ── Validation ────────────────────────────────────────
    Case("missing start/end", "POST", "/analyze", section="Validation",
         body={"tenant_id": TENANT}, expect=422),
    Case("sensitivity out of range", "POST", "/analyze", section="Validation",
         body={**base(), "sensitivity": 99}, expect=422),
    Case("slo target > 1", "POST", "/slo/burn", section="Validation",
         body={**base(), "service": "payment-service", "target_availability": 1.5}, expect=422),
]


async def run_case(client: httpx.AsyncClient, case: Case) -> tuple[bool, str, Any]:
    attempt = 0
    last_exc: Exception | None = None
    while attempt < 2:
        try:
            if case.method == "GET":
                r = await client.get(case.path, params=case.params)
            elif case.method == "DELETE":
                r = await client.delete(case.path, params=case.params)
            else:
                r = await client.request(case.method, case.path, json=case.body or None,
                                         params=case.params)
            ok = r.status_code == case.expect
            body: Any = None
            try:
                body = r.json()
            except Exception:
                body = r.text
            if ok:
                return True, "", body
            # failure, include response in detail
            if isinstance(body, (dict, list)):
                detail = f"{r.status_code} {r.reason_phrase}: {body}"
            else:
                detail = f"{r.status_code} {r.reason_phrase}: {body}"
            return False, detail, body
        except httpx.TransportError as exc:
            last_exc = exc
            attempt += 1
            if attempt < 2:
                await asyncio.sleep(0.1)
                continue
            return False, f"transport error: {exc}", None
        except Exception as e:
            return False, str(e), None
    return False, str(last_exc), None


async def main():
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Run API test cases")
    parser.add_argument("--section", help="only run cases from this section name")
    parser.add_argument("--label", help="only run the case with this exact label")
    args = parser.parse_args()
    selected: list[Case] = []
    for c in CASES:
        if args.section and c.section != args.section:
            continue
        if args.label and c.label != args.label:
            continue
        selected.append(c)
    if not selected:
        print("no matching cases (check --section or --label)")
        sys.exit(1)

    passed = failed = 0
    current_section = ""

    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30) as client:
        for case in selected:
            if case.section != current_section:
                current_section = case.section
                print(f"\n── {current_section} {'─' * max(0, 44 - len(current_section))}")

            ok, detail, body = await run_case(client, case)
            if body is not None:
                try:
                    pretty = json.dumps(body, indent=2)
                except Exception:
                    pretty = str(body)
            else:
                pretty = "<no response>"

            if ok:
                passed += 1
                print(f"  ✓ PASS  {case.method} {case.path} — {case.label}")
                print(f"         response:\n{pretty}")
            else:
                failed += 1
                print(f"  ✗ FAIL  {case.method} {case.path} — {case.label} (expected {case.expect})")
                if detail:
                    print(f"         {detail}")
                print(f"         response:\n{pretty}")

    total = passed + failed
    print(f"\n{'━' * 43}")
    print(f"  Results: {passed} passed / {failed} failed / {total} total")
    print(f"  {'All tests passed ✓' if failed == 0 else f'{failed} test(s) failed ✗'}")
    print(f"{'━' * 43}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
