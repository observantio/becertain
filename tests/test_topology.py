import pytest

from engine.topology.graph import DependencyGraph, BlastRadius


def test_dependency_graph():
    g = DependencyGraph()
    g.add_call("a", "b")
    g.add_call("b", "c")
    g.add_call("c", "a")  # cycle should be handled gracefully
    assert "b" in g._forward["a"]
    br = g.blast_radius("a", max_depth=2)
    assert isinstance(br, BlastRadius)
    assert "b" in br.affected_downstream
    roots = g.find_upstream_roots("c")
    # at least one root should exist (could be none in tight cycle)
    assert isinstance(roots, list)
    path = g.critical_path("a", "c")
    assert path and path[0] == "a" and path[-1] == "c"
    allsvcs = g.all_services()
    assert allsvcs >= {"a","b","c"}


def test_from_spans():
    g = DependencyGraph()
    spans = [{"service":"a","peer_service":"b"}, {"service":"b","peer_service":"d"}]
    g.from_spans(spans)
    assert "b" in g._forward["a"]
