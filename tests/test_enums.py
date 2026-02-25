"""
Test cases for enums used in the analysis engine, including Severity, Signal, ChangeType, and RcaCategory, validating their properties and relationships.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import pytest

from engine.enums import Severity, Signal, ChangeType, RcaCategory


def test_severity_from_score_and_weight():
    assert Severity.from_score(0.8) == Severity.critical
    assert Severity.from_score(0.5) == Severity.high
    assert Severity.from_score(0.3) == Severity.medium
    assert Severity.from_score(0.1) == Severity.low
    assert Severity.low.weight() < Severity.medium.weight() < Severity.high.weight() < Severity.critical.weight()


def test_signal_enum():
    assert list(Signal) == [Signal.metrics, Signal.logs, Signal.traces, Signal.events]


def test_change_type_and_rca_category():
    assert ChangeType.spike.value == "spike"
    assert RcaCategory.deployment.value == "deployment"
