from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Tuple

from datasources.provider import DataSourceProvider

log = logging.getLogger(__name__)


async def _scrape_and_fill(
    provider: DataSourceProvider,
    queries: List[str],
    start: int,
    end: int,
) -> List[Tuple[str, Dict[str, Any]]]:
    scrape_func = getattr(provider.metrics, "scrape", None)
    if not scrape_func or not callable(scrape_func):
        return []

    try:
        text = await scrape_func()
    except Exception:
        return []

    metrics: Dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].split("{", 1)[0]
        try:
            metrics[name] = float(parts[1])
        except ValueError:
            continue

    if not metrics:
        return []

    results: List[Tuple[str, Dict[str, Any]]] = []
    for q in queries:
        candidates: List[str] = []
        m = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)$", q)
        if m:
            candidates.append(m.group(1))
        m = re.match(r"^rate\(([a-zA-Z_:][a-zA-Z0-9_:]*)\[.*\]\)", q)
        if m:
            candidates.append(m.group(1))
        for metric_name in metrics:
            if metric_name in q:
                candidates.append(metric_name)

        for name in set(candidates):
            if name in metrics:
                val = metrics[name]
                results.append((q, {
                    "status": "success",
                    "data": {
                        "result": [{
                            "metric": {"__name__": name},
                            "values": [[start, val], [end, val]],
                        }]
                    },
                }))
    return results


async def fetch_metrics(
    provider: DataSourceProvider,
    queries: List[str],
    start: int,
    end: int,
    step: str,
) -> List[Tuple[str, Dict[str, Any]]]:
    raw = await asyncio.gather(
        *[provider.query_metrics(query=q, start=start, end=end, step=step) for q in queries],
        return_exceptions=True,
    )

    pairs: List[Tuple[str, Dict[str, Any]]] = []
    all_empty = True
    for q, r in zip(queries, raw):
        if isinstance(r, Exception):
            log.warning("fetch_metrics query %s failed: %s", q, r)
            continue
        cnt = len(r.get("data", {}).get("result", []))
        log.info("fetch_metrics query %s returned %d series", q, cnt)
        pairs.append((q, r))
        if cnt > 0:
            all_empty = False

    if pairs and all_empty:
        scraped = await _scrape_and_fill(provider, queries, start, end)
        if scraped:
            return scraped

    return pairs