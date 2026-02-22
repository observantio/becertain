# traces/__init__.py
from engine.traces.latency import analyze
from engine.traces.errors import detect_propagation

__all__ = ["analyze", "detect_propagation"]