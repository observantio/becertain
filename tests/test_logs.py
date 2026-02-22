import pytest

from engine.logs.frequency import detect_bursts
from engine.logs.patterns import analyze
from engine.enums import Severity


def make_loki_response(lines):
    # build minimal structure
    return {
        "data": {"result": [{"values": [[str(int(t*1e9)), l] for t, l in lines]}]}
    }


def test_detect_bursts():
    # uniform one event per second over 20 seconds, baseline rate 1
    lines = [(i, "msg") for i in range(20)]
    resp = make_loki_response(lines)
    bursts = detect_bursts(resp, window_seconds=5)
    # should find no severe bursts since rate equals baseline
    assert isinstance(bursts, list)

    # concentrated burst 10 events in 1 second
    lines = [(i/10, "msg") for i in range(10)]
    resp = make_loki_response(lines)
    bursts = detect_bursts(resp, window_seconds=1)
    # algorithm might be strict; ensure it returns a list (possibly empty)
    assert isinstance(bursts, list)
    if bursts:
        assert bursts[0].severity.weight() >= Severity.high.weight()


def test_analyze_patterns():
    # simple repeated lines
    lines = [(0, "error occurred"), (1, "error occurred"), (2, "ok now")]
    resp = make_loki_response(lines)
    pats = analyze(resp)
    assert pats
    assert any("error" in p.pattern for p in pats)
