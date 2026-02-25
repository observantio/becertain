"""
Test cases for changepoint detection logic in the analysis engine, including CUSUM parameter sensitivity and oscillation detection behavior.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import pytest
import numpy as np

from config import settings
from engine.changepoint.cusum import _detect_oscillation, detect


def test_cusum_k_and_density():
    arr = np.array([0, 0, 0, 10, 0, 0, 0], dtype=float)
    flags = _detect_oscillation(arr, window=4)
    assert flags == []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "cusum_oscillation_density_cutoff", 0.0)
    flags2 = _detect_oscillation(arr, window=4)
    assert isinstance(flags2, list)
    monkeypatch.undo()


def test_detect_uses_settings(monkeypatch):
    ts = list(range(10))
    vals = [1] * 9 + [20]

    monkeypatch.setattr(settings, "cusum_k", 10.0)
    pts_high_k = detect(ts, vals, threshold_sigma=0.1)
    monkeypatch.setattr(settings, "cusum_k", 0.1)
    pts_low_k = detect(ts, vals, threshold_sigma=0.1)

    assert len(pts_low_k) >= len(pts_high_k)
