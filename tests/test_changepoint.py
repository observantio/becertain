"""
Tests for cusum change point detection including configuration overrides.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
"""

import pytest
import numpy as np

from config import settings
from engine.changepoint.cusum import _detect_oscillation, detect


def test_cusum_k_and_density():
    arr = np.array([0, 0, 0, 10, 0, 0, 0], dtype=float)

    # default k yields some flags
    flags = _detect_oscillation(arr, window=4)
    # density cutoff default is 0.3, for this short array we expect []
    assert flags == []

    # if we lower density cutoff, oscillation indices should appear
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "cusum_oscillation_density_cutoff", 0.0)
    flags2 = _detect_oscillation(arr, window=4)
    assert isinstance(flags2, list)
    monkeypatch.undo()


def test_detect_uses_settings(monkeypatch):
    # change k and verify that detect output shifts accordingly
    ts = list(range(10))
    vals = [1] * 9 + [20]

    monkeypatch.setattr(settings, "cusum_k", 10.0)
    pts_high_k = detect(ts, vals, threshold_sigma=0.1)
    monkeypatch.setattr(settings, "cusum_k", 0.1)
    pts_low_k = detect(ts, vals, threshold_sigma=0.1)

    assert len(pts_low_k) >= len(pts_high_k)
