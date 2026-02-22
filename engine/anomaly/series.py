from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, Tuple

import numpy as np

log = logging.getLogger(__name__)

def iter_series(
    mimir_response: Dict[str, Any],
) -> Iterator[Tuple[str, list, list]]:
    """Yield (metric_label, timestamps, values) from a Prometheus query_range response."""
    try:
        for result in mimir_response.get("data", {}).get("result", []):
            metric = result.get("metric", {})
            label = (
                metric.get("__name__")
                or metric.get("job")
                or next(iter(metric.values()), None)
                or str(metric)
            )
            pairs = result.get("values", [])
            if not pairs:
                continue
            ts = [float(p[0]) for p in pairs]
            vals = []
            for p in pairs:
                try:
                    vals.append(float(p[1]))
                except (ValueError, TypeError):
                    vals.append(float("nan"))
            yield label, ts, vals
    except Exception as exc:
        log.warning("Failed to parse Mimir response: %s", exc)