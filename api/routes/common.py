"""
Shared utilities and dependencies for API route modules.

Provides a centralized place for creating data source providers, handling
common error translation to HTTP responses, and other helpers used across
multiple routers. This keeps individual route files thin and avoids repeating
boilerplate logic.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

from typing import Any, Awaitable, TypeVar

from fastapi import HTTPException

from datasources.data_config import DataSourceSettings
from datasources.provider import DataSourceProvider


_T = TypeVar("_T")
_providers: dict[str, DataSourceProvider] = {}


def get_provider(tenant_id: str) -> DataSourceProvider:
    provider = _providers.get(tenant_id)
    if provider is None:
        provider = DataSourceProvider(tenant_id=tenant_id, settings=DataSourceSettings())
        _providers[tenant_id] = provider
    return provider


async def close_providers() -> None:
    providers = list(_providers.values())
    _providers.clear()
    for provider in providers:
        await provider.aclose()


async def safe_call(coro: Awaitable[_T], status_code: int = 502) -> _T:
    try:
        return await coro
    except Exception as exc: 
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def to_nanoseconds(ts: int) -> int:
    return ts * 1_000_000_000
