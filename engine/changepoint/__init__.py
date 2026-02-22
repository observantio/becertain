# changepoint/__init__.py
from engine.changepoint.cusum import ChangePoint, detect

__all__ = ["ChangePoint", "detect"]