"""
Test Suite for Engine Registry (signal weights)

This mirrors some of the logic in store.registry but exercises the engine-level
TenantState/Registry where weights are keyed by Signal and a serializable
view is available. It also covers the bugfixes around default coercion and
string-signal acceptance.
"""

import pytest

from engine import registry as ereg
from engine.enums import Signal
from store import weights as wstore


@pytest.mark.asyncio
async def test_engine_registry_defaults_and_updates(monkeypatch):
    tid = "tenantX"
    saved = {}

    async def fake_load(t):
        return saved.get(t)

    async def fake_save(t, weights, update_count):
        saved[t] = {"weights": weights, "update_count": update_count}

    async def fake_delete(t):
        saved.pop(t, None)

    monkeypatch.setattr(wstore, "load", fake_load)
    monkeypatch.setattr(wstore, "save", fake_save)
    monkeypatch.setattr(wstore, "delete", fake_delete)

    reg = ereg.TenantRegistry()

    # initial state should coerce DEFAULT_WEIGHTS strings to Signal keys
    state = await reg.get_state(tid)
    assert state.update_count == 0
    # weights property returns internal representation (Signal keys)
    assert set(state.weights.keys()) == {Signal.metrics, Signal.logs, Signal.traces}
    # serializable form exposes string values
    assert state.weights_serializable == {"metrics": 0.3, "logs": 0.35, "traces": 0.35}

    # calling update_weight with a string should be accepted
    await reg.update_weight(tid, "metrics", True)
    assert saved[tid]["weights"]["metrics"] > 0.3
    assert saved[tid]["update_count"] == 1

    # the state still internally uses Signal key
    state2 = await reg.get_state(tid)
    assert Signal.metrics in state2.weights

    # increasing the count and resetting
    state2.update_weight(Signal.logs, False)
    assert state2.update_count == 2
    await reg.reset_weights(tid)
    state3 = await reg.get_state(tid)
    assert state3.update_count == 0
    assert state3.weights_serializable == {"metrics": 0.3, "logs": 0.35, "traces": 0.35}
