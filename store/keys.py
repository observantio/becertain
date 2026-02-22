from __future__ import annotations

import hashlib


def _slug(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()[:12]


def baseline(tenant_id: str, metric_name: str) -> str:
    return f"bc:{tenant_id}:baseline:{_slug(metric_name)}"


def weights(tenant_id: str) -> str:
    return f"bc:{tenant_id}:weights"


def granger(tenant_id: str, service: str) -> str:
    return f"bc:{tenant_id}:granger:{_slug(service)}"


def events(tenant_id: str) -> str:
    return f"bc:{tenant_id}:events"