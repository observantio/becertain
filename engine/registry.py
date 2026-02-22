"""
Registry for Tenant-Specific Weights and Events

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

from __future__ import annotations

import logging
from typing import Dict, List, Union

from engine.enums import Signal
from store import events as event_store, weights as weight_store
from engine.events.registry import DeploymentEvent
from config import DEFAULT_WEIGHTS, REGISTRY_ALPHA

log = logging.getLogger(__name__)

_SIGNAL_KEYS: tuple[Signal, ...] = (Signal.metrics, Signal.logs, Signal.traces)


def _coerce_weights(raw: dict) -> Dict[Signal, float]:
    return {Signal(k): float(v) for k, v in raw.items() if k in Signal._value2member_map_}


def _serialize_weights(weights: Dict[Signal, float]) -> Dict[str, float]:
    return {k.value: v for k, v in weights.items()}


class TenantState:
    __slots__ = ("_weights", "_update_count")

    def __init__(self, weights: Dict[Signal, float], update_count: int) -> None:
        self._weights: Dict[Signal, float] = _coerce_weights(weights)
        self._update_count = update_count

    @property
    def weights(self) -> Dict[Signal, float]:
        return dict(self._weights)

    @property
    def weights_serializable(self) -> Dict[str, float]:
        return _serialize_weights(self._weights)

    @property
    def update_count(self) -> int:
        return self._update_count

    def update_weight(self, signal: Signal, was_correct: bool) -> None:
        reward = 1.0 if was_correct else 0.0
        current = self._weights.get(signal, DEFAULT_WEIGHTS.get(signal, 1.0 / len(_SIGNAL_KEYS)))
        self._weights[signal] = (1 - REGISTRY_ALPHA) * current + REGISTRY_ALPHA * reward
        self._normalize()
        self._update_count += 1

    def weighted_confidence(
        self,
        metric_score: float,
        log_score: float,
        trace_score: float,
    ) -> float:
        w = self._weights
        default = DEFAULT_WEIGHTS
        return round(
            w.get(Signal.metrics, default[Signal.metrics]) * metric_score
            + w.get(Signal.logs, default[Signal.logs]) * log_score
            + w.get(Signal.traces, default[Signal.traces]) * trace_score,
            4,
        )

    def _normalize(self) -> None:
        total = sum(self._weights.values()) or 1.0
        for k in self._weights:
            self._weights[k] = self._weights[k] / total

    def reset(self) -> None:
        self._weights = _coerce_weights(DEFAULT_WEIGHTS)
        self._update_count = 0


class TenantRegistry:
    def __init__(self) -> None:
        self._states: Dict[str, TenantState] = {}

    async def get_state(self, tenant_id: str) -> TenantState:
        if tenant_id not in self._states:
            stored = await weight_store.load(tenant_id)
            if stored:
                state = TenantState(
                    weights=_coerce_weights(stored["weights"]),
                    update_count=stored.get("update_count", 0),
                )
            else:
                state = TenantState(weights=_coerce_weights(DEFAULT_WEIGHTS), update_count=0)
            self._states[tenant_id] = state
        return self._states[tenant_id]

    async def update_weight(
        self, tenant_id: str, signal: Union[Signal, str], was_correct: bool
    ) -> TenantState:
        if isinstance(signal, str):
            try:
                signal = Signal(signal)
            except ValueError:
                raise
        state = await self.get_state(tenant_id)
        state.update_weight(signal, was_correct)
        await weight_store.save(tenant_id, state.weights_serializable, state.update_count)
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
        events = await event_store.load(tenant_id)
        return [e for e in events if start <= e["timestamp"] <= end]

    def evict(self, tenant_id: str) -> None:
        self._states.pop(tenant_id, None)


_registry = TenantRegistry()


def get_registry() -> TenantRegistry:
    return _registry