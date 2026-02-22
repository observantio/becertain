# anomaly/__init__.py
from engine.anomaly.detection import detect
from engine.anomaly.series import iter_series

__all__ = ["detect", "iter_series"]