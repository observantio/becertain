from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from engine.enums import Signal
from config import DEFAULT_WEIGHTS, REGISTRY_ALPHA

# use the central defaults defined in config


@dataclass
class SignalWeights:
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    alpha: float = REGISTRY_ALPHA
    update_count: int = 0

    def update(self, signal: Signal, was_correct: bool) -> None:
        reward = 1.0 if was_correct else 0.0
        current = self.weights.get(signal, 1.0 / len(Signal))
        self.weights[signal] = round(
            (1 - self.alpha) * current + self.alpha * reward, 4
        )
        self._normalize()
        self.update_count += 1

    def _normalize(self) -> None:
        total = sum(self.weights.values()) or 1.0
        for k in self.weights:
            self.weights[k] = round(self.weights[k] / total, 4)

    def get(self, signal: Signal) -> float:
        return self.weights.get(signal, 1.0 / len(Signal))

    def weighted_confidence(
        self,
        metric_score: float,
        log_score: float,
        trace_score: float,
    ) -> float:
        return round(
            self.get(Signal.metrics) * metric_score
            + self.get(Signal.logs) * log_score
            + self.get(Signal.traces) * trace_score,
            3,
        )

    def reset(self) -> None:
        self.weights = dict(DEFAULT_WEIGHTS)
        self.update_count = 0


_global_weights = SignalWeights()


def get_weights() -> SignalWeights:
    return _global_weights