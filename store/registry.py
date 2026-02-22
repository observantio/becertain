"""
Registry of recent deployment events for each tenant, stored in Redis with a capped list.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import logging
from typing import Dict, List

from engine.enums import Signal
from store import events as event_store, weights as weight_store
from engine.events.registry import DeploymentEvent
from config import REGISTRY_ALPHA, DEFAULT_WEIGHTS

log = logging.getLogger(__name__)


class TenantState:
    __slots__ = ("_weights", "_update_count")

    def __init__(self, weights: Dict[str, float], update_count: int) -> None:
        self._weights: Dict[Signal, float] = {
            Signal[k] if isinstance(k, str) else k: v
            for k, v in weights.items()
        }
        self._update_count = update_count

    @property
    def weights(self) -> Dict[str, float]:
        return {k.name: v for k, v in self._weights.items()}

    @property
    def update_count(self) -> int:
        return self._update_count

    def update_weight(self, signal: Signal, was_correct: bool) -> None:
        reward = 1.0 if was_correct else 0.0
        current = self._weights.get(signal, 1.0 / 3)
        self._weights[signal] = round((1 - REGISTRY_ALPHA) * current + REGISTRY_ALPHA * reward, 4)
        self._normalize()
        self._update_count += 1

    def weighted_confidence(
        self,
        metric_score: float,
        log_score: float,
        trace_score: float,
    ) -> float:
        return round(
            self._weights.get(Signal.metrics, 0.30) * metric_score
            + self._weights.get(Signal.logs,    0.35) * log_score
            + self._weights.get(Signal.traces,  0.35) * trace_score,
            3,
        )

    def _normalize(self) -> None:
        total = sum(self._weights.values()) or 1.0
        for k in self._weights:
            self._weights[k] = round(self._weights[k] / total, 4)

    def reset(self) -> None:
        self._weights = {
            Signal[k] if isinstance(k, str) else k: v
            for k, v in DEFAULT_WEIGHTS.items()
        }
        self._update_count = 0


class TenantRegistry:
    def __init__(self) -> None:
        self._states: Dict[str, TenantState] = {}

    async def get_state(self, tenant_id: str) -> TenantState:
        if tenant_id not in self._states:
            stored = await weight_store.load(tenant_id)
            if stored:
                state = TenantState(
                    weights=stored["weights"],
                    update_count=stored.get("update_count", 0),
                )
            else:
                state = TenantState(weights=dict(DEFAULT_WEIGHTS), update_count=0)
            self._states[tenant_id] = state
        return self._states[tenant_id]

    async def update_weight(self, tenant_id: str, signal: Signal, was_correct: bool) -> TenantState:
        state = await self.get_state(tenant_id)
        state.update_weight(signal, was_correct)
        await weight_store.save(tenant_id, state.weights, state.update_count)
        return state

    async def reset_weights(self, tenant_id: str) -> TenantState:
        state = await self.get_state(tenant_id)
        state.reset()
        await weight_store.delete(tenant_id)
        self._states.pop(tenant_id, None)
        return state

    async def register_event(self, tenant_id: str, event: DeploymentEvent) -> None:
        await event_store.append(tenant_id, event)

    async def get_events(self, tenant_id: str) -> List[dict]:
        return await event_store.load(tenant_id)

    async def clear_events(self, tenant_id: str) -> None:
        await event_store.clear(tenant_id)

    async def events_in_window(self, tenant_id: str, start: float, end: float) -> List[dict]:
        return [
            e for e in await event_store.load(tenant_id)
            if start <= e["timestamp"] <= end
        ]


_registry = TenantRegistry()


def get_registry() -> TenantRegistry:
    return _registry