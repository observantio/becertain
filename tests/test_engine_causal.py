import pytest

from engine.causal.graph import CausalGraph, InterventionResult
from engine.causal.bayesian import score as bayesian_score
from engine.causal.granger import granger_pair_analysis, granger_multiple_pairs, GrangerResult


def test_bayesian_score_consistency():
    # simple check that outputs sum to 1 and highest posterior corresponds to evidence
    results = bayesian_score(True, False, False, False, False)
    assert abs(sum(r.posterior for r in results) - 1.0) < 1e-6
    # deployment category should top when has_deployment_event True
    assert results[0].category.name == "deployment"


def test_causal_graph_basic():
    g = CausalGraph()
    g.add_edge("a", "b", 0.5)
    g.add_edge("b", "c", 0.4)
    # topological order should start with a
    order = g.topological_sort()
    assert order[0] == "a"
    assert g.root_causes() == ["a"]
    inter = g.simulate_intervention("a", max_depth=2)
    assert isinstance(inter, InterventionResult)
    assert "b" in inter.expected_effect_on
    # common causes of b and c include a
    assert g.find_common_causes("b", "c") == ["a"]


def test_granger_pair_and_all():
    # trivial data where cause leads effect with lag
    # need at least max_lag + 10 points (here 11) for the algorithm
    cause = list(range(15))
    effect = [0, 0] + list(range(13))
    res = granger_pair_analysis("c", cause, "e", effect, max_lag=1)
    assert isinstance(res, GrangerResult)
    assert res.cause_metric == "c"
    assert res.effect_metric == "e"
    allr = granger_multiple_pairs({"c": cause, "e": effect})
    assert allr
    assert allr[0].cause_metric == "c"
