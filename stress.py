#!/usr/bin/env python3

"""
Script to perform concurrent stress testing of the /analyze endpoint.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class RunConfig:
    base_url: str
    endpoint: str
    tenants: list[str]
    start: int
    end: int
    step: str
    concurrency: int
    requests: int
    timeout: float
    warmup: int
    services: list[str]
    sensitivity: float | None


def _parse_args() -> RunConfig:
    now = int(time.time())

    parser = argparse.ArgumentParser(description="Concurrent stress test for /analyze")
    parser.add_argument("--base-url", default="http://localhost:4322/api/v1", help="API base URL")
    parser.add_argument("--endpoint", default="/analyze", help="Endpoint path")
    parser.add_argument(
        "--tenants",
        default="Av45ZchZsQdKjN8XyG",
        help="Comma-separated tenant ids. Requests are round-robin distributed.",
    )
    parser.add_argument("--start", type=int, default=now - 3600, help="Start timestamp (seconds)")
    parser.add_argument("--end", type=int, default=now, help="End timestamp (seconds)")
    parser.add_argument("--step", default="15s", help="Metrics step")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--requests", type=int, default=50, help="Total measured requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout (seconds)")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup requests (not measured)")
    parser.add_argument(
        "--services",
        default="payment-service",
        help="Comma-separated services list (empty string for global)",
    )
    parser.add_argument("--sensitivity", type=float, default=None, help="Optional analyze sensitivity")

    args = parser.parse_args()

    tenants = [t.strip() for t in args.tenants.split(",") if t.strip()]
    if not tenants:
        raise SystemExit("--tenants must include at least one tenant id")

    services = [s.strip() for s in args.services.split(",") if s.strip()] if args.services else []

    if args.start >= args.end:
        raise SystemExit("invalid range: --start must be less than --end")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")
    if args.requests < 1:
        raise SystemExit("--requests must be >= 1")
    if args.warmup < 0:
        raise SystemExit("--warmup must be >= 0")

    return RunConfig(
        base_url=args.base_url.rstrip("/"),
        endpoint=args.endpoint,
        tenants=tenants,
        start=args.start,
        end=args.end,
        step=args.step,
        concurrency=args.concurrency,
        requests=args.requests,
        timeout=args.timeout,
        warmup=args.warmup,
        services=services,
        sensitivity=args.sensitivity,
    )


def _payload(cfg: RunConfig, tenant_id: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "tenant_id": tenant_id,
        "start": cfg.start,
        "end": cfg.end,
        "step": cfg.step,
        "services": cfg.services,
    }
    if cfg.sensitivity is not None:
        body["sensitivity"] = cfg.sensitivity
    return body


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = rank - lower
    return sorted_values[lower] * (1.0 - frac) + sorted_values[upper] * frac


async def _one_request(client: httpx.AsyncClient, cfg: RunConfig, idx: int) -> tuple[float, int, str | None, int]:
    tenant_id = cfg.tenants[idx % len(cfg.tenants)]
    body = _payload(cfg, tenant_id)

    t0 = time.perf_counter()
    try:
        resp = await client.post(cfg.endpoint, json=body)
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return latency_ms, 0, f"transport:{type(exc).__name__}", 0

    latency_ms = (time.perf_counter() - t0) * 1000.0
    warning_count = 0
    err = None
    if resp.status_code != 200:
        err = f"http:{resp.status_code}"
    else:
        try:
            data = resp.json()
            warning_count = len(data.get("analysis_warnings") or [])
        except Exception:
            pass

    return latency_ms, resp.status_code, err, warning_count


async def _run_phase(client: httpx.AsyncClient, cfg: RunConfig, count: int, start_idx: int) -> list[tuple[float, int, str | None, int]]:
    next_index = start_idx
    lock = asyncio.Lock()
    results: list[tuple[float, int, str | None, int]] = []

    async def worker() -> None:
        nonlocal next_index
        while True:
            async with lock:
                if next_index >= start_idx + count:
                    return
                idx = next_index
                next_index += 1
            results.append(await _one_request(client, cfg, idx))

    workers = [asyncio.create_task(worker()) for _ in range(cfg.concurrency)]
    await asyncio.gather(*workers)
    return results


def _print_summary(cfg: RunConfig, elapsed_s: float, results: list[tuple[float, int, str | None, int]]) -> None:
    latencies = [r[0] for r in results]
    codes = Counter(r[1] for r in results)
    errors = Counter(r[2] for r in results if r[2])
    warnings = sum(r[3] for r in results)

    sorted_lat = sorted(latencies)
    success = sum(1 for _, code, _, _ in results if code == 200)
    rps = len(results) / elapsed_s if elapsed_s > 0 else 0.0

    print("\nStress test complete")
    print(f"target        : {cfg.base_url}{cfg.endpoint}")
    print(f"tenants       : {', '.join(cfg.tenants)}")
    print(f"requests      : {len(results)}")
    print(f"concurrency   : {cfg.concurrency}")
    print(f"success       : {success}/{len(results)} ({(success/len(results))*100:.1f}%)")
    print(f"duration      : {elapsed_s:.3f}s")
    print(f"throughput    : {rps:.2f} req/s")
    print(f"latency avg   : {statistics.fmean(latencies):.2f} ms")
    print(f"latency p50   : {_percentile(sorted_lat, 0.50):.2f} ms")
    print(f"latency p95   : {_percentile(sorted_lat, 0.95):.2f} ms")
    print(f"latency p99   : {_percentile(sorted_lat, 0.99):.2f} ms")
    print(f"warnings total: {warnings}")
    print(f"status codes  : {dict(sorted(codes.items(), key=lambda kv: kv[0]))}")
    if errors:
        print(f"errors        : {dict(errors.most_common())}")


async def main() -> None:
    cfg = _parse_args()

    timeout = httpx.Timeout(cfg.timeout)
    async with httpx.AsyncClient(base_url=cfg.base_url, timeout=timeout) as client:
        if cfg.warmup:
            print(f"Running warmup: {cfg.warmup} request(s)...")
            await _run_phase(client, cfg, cfg.warmup, 0)

        print(f"Running measured phase: {cfg.requests} request(s), concurrency={cfg.concurrency}...")
        t0 = time.perf_counter()
        measured = await _run_phase(client, cfg, cfg.requests, cfg.warmup)
        elapsed = time.perf_counter() - t0

    _print_summary(cfg, elapsed, measured)


if __name__ == "__main__":
    asyncio.run(main())
