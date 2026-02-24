"""
Series iteration logic for processing Mimir query responses, extracting metric labels and corresponding timestamp-value pairs, to facilitate downstream analysis and anomaly detection on time series data.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, Tuple, Union

log = logging.getLogger(__name__)

_LABEL_PRIORITY = (
    "service",
    "service_name",
    "service.name",
    "job",
    "instance",
    "pod",
    "namespace",
    "operation",
    "method",
    "status_code",
)


def iter_series(
    mimir_response: Union[Dict[str, Any], Tuple[Any, Dict[str, Any]]],
) -> Iterator[Tuple[str, list, list]]:
    if isinstance(mimir_response, tuple):
        if len(mimir_response) == 2 and isinstance(mimir_response[1], dict):
            mimir_response = mimir_response[1]
        else:
            log.warning("iter_series received unexpected tuple shape: %r", mimir_response)
            return

    if not isinstance(mimir_response, dict):
        log.warning("iter_series expected dict, got %s", type(mimir_response).__name__)
        return

    results = mimir_response.get("data", {}).get("result", [])
    if not isinstance(results, list):
        log.warning("iter_series: 'data.result' is not a list: %s", type(results).__name__)
        return

    for result in results:
        if not isinstance(result, dict):
            continue

        metric = result.get("metric", {})
        base = str(metric.get("__name__") or "metric")
        label_parts: list[str] = []
        for key in _LABEL_PRIORITY:
            value = metric.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            label_parts.append(f"{key}={text}")
            if len(label_parts) >= 3:
                break
        label = f"{base}{{{','.join(label_parts)}}}" if label_parts else base

        pairs = result.get("values", [])
        if not pairs:
            continue

        ts: list[float] = []
        vals: list[float] = []
        for p in pairs:
            try:
                ts.append(float(p[0]))
                vals.append(float(p[1]))
            except (ValueError, TypeError, IndexError):
                ts.append(float("nan"))
                vals.append(float("nan"))

        yield label, ts, vals
