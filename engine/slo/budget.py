from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetStatus:
    service: str
    target_availability: float
    current_availability: float
    budget_used_pct: float
    remaining_minutes: float
    on_track: bool


_MONTH_MINUTES = 30 * 24 * 60


def remaining_minutes(
    service: str,
    error_counts: list[float],
    total_counts: list[float],
    target_availability: float = 0.999,
) -> BudgetStatus:
    total = sum(total_counts)
    errors = sum(error_counts)

    if total == 0:
        return BudgetStatus(
            service=service,
            target_availability=target_availability,
            current_availability=1.0,
            budget_used_pct=0.0,
            remaining_minutes=_MONTH_MINUTES * (1 - target_availability),
            on_track=True,
        )

    current_avail = 1.0 - (errors / total)
    allowed_downtime = _MONTH_MINUTES * (1.0 - target_availability)
    used_downtime = _MONTH_MINUTES * (errors / total)
    remaining = max(0.0, allowed_downtime - used_downtime)
    budget_used = min(100.0, (used_downtime / allowed_downtime * 100) if allowed_downtime else 100.0)

    return BudgetStatus(
        service=service,
        target_availability=target_availability,
        current_availability=round(current_avail, 6),
        budget_used_pct=round(budget_used, 2),
        remaining_minutes=round(remaining, 1),
        on_track=budget_used < 100.0,
    )