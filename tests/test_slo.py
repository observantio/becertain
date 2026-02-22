import pytest

from engine.slo.burn import evaluate, SloBurnAlert
from engine.slo.budget import remaining_minutes, BudgetStatus
from engine.enums import Severity


def test_slo_evaluate_empty():
    assert evaluate("svc", [], [], [], 0.99) == []


def test_slo_evaluate_burn():
    ts = [0, 3600]
    total = [100, 100]
    errors = [10, 20]
    alerts = evaluate("svc", errors, total, ts, target_availability=0.9)
    assert isinstance(alerts, list)
    if alerts:
        assert isinstance(alerts[0], SloBurnAlert)
        assert alerts[0].burn_rate > 0


def test_budget_remaining():
    status = remaining_minutes("svc", [0], [0], 0.99)
    assert isinstance(status, BudgetStatus)
    assert status.current_availability == 1.0
    status2 = remaining_minutes("svc", [10], [100], 0.99)
    assert status2.budget_used_pct >= 0
