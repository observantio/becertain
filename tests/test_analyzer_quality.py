from __future__ import annotations

from api.responses import MetricAnomaly, RootCause as RootCauseModel
from engine.analyzer import _limit_analyzer_output, _select_granger_series, _to_root_cause_model
from engine.causal.granger import GrangerResult
from engine.changepoint import ChangePoint
from engine.enums import ChangeType, RcaCategory, Severity, Signal
from engine.ml.clustering import AnomalyCluster
from engine.ml.ranking import RankedCause
from engine.rca.hypothesis import RootCause


def _anomaly(idx: int, severity: Severity) -> MetricAnomaly:
    return MetricAnomaly(
        metric_name=f"m{idx}",
        timestamp=1000.0 + idx,
        value=float(idx),
        change_type=ChangeType.spike,
        z_score=float(idx),
        mad_score=float(idx) / 2.0,
        isolation_score=0.5,
        expected_range=(0.0, 10.0),
        severity=severity,
        description=f"m{idx} anomaly",
    )


def _ranked(idx: int, final_score: float) -> RankedCause:
    rc = RootCause(
        hypothesis=f"cause-{idx}",
        confidence=min(1.0, max(0.0, final_score)),
        severity=Severity.medium,
        category=RcaCategory.unknown,
        evidence=[],
        contributing_signals=["metrics"],
        affected_services=[],
        recommended_action="investigate",
    )
    return RankedCause(root_cause=rc, ml_score=final_score, final_score=final_score, feature_importance={})


def test_to_root_cause_model_clamps_invalid_confidence():
    rc = _to_root_cause_model(
        {
            "hypothesis": "test",
            "confidence": "nan",
            "evidence": [],
            "contributing_signals": ["metrics", "log:burst"],
            "recommended_action": "act",
            "severity": "low",
        }
    )
    assert isinstance(rc, RootCauseModel)
    assert rc.confidence == 0.0
    assert Signal.metrics in rc.contributing_signals
    assert Signal.logs in rc.contributing_signals


def test_limit_analyzer_output_caps_noise_lists():
    anomalies = [_anomaly(i, Severity.critical if i % 2 else Severity.low) for i in range(500)]
    change_points = [
        ChangePoint(
            index=i,
            timestamp=10.0 + i,
            value_before=1.0,
            value_after=2.0,
            magnitude=float(i),
            change_type=ChangeType.shift,
            metric_name=f"c{i}",
        )
        for i in range(400)
    ]
    root_causes = [
        RootCauseModel(
            hypothesis=f"h{i}",
            confidence=min(1.0, i / 20.0),
            evidence=[],
            contributing_signals=[Signal.metrics],
            recommended_action="x",
            severity=Severity.low,
        )
        for i in range(40)
    ]
    ranked = [_ranked(i, i / 40.0) for i in range(40)]
    clusters = [
        AnomalyCluster(
            cluster_id=i,
            members=anomalies[: (i + 1)],
            centroid_timestamp=1000.0,
            centroid_value=1.0,
            metric_names=["m"],
            size=i + 1,
        )
        for i in range(50)
    ]
    granger = [
        GrangerResult(
            cause_metric=f"a{i}",
            effect_metric=f"b{i}",
            max_lag=2,
            f_statistic=1.0,
            p_value=0.01,
            is_causal=True,
            strength=i / 50.0,
        )
        for i in range(220)
    ]
    warnings: list[str] = []

    (
        anomalies_limited,
        cps_limited,
        causes_limited,
        ranked_limited,
        clusters_limited,
        granger_limited,
    ) = _limit_analyzer_output(
        metric_anomalies=anomalies,
        change_points=change_points,
        root_causes=root_causes,
        ranked_causes=ranked,
        anomaly_clusters=clusters,
        granger_results=granger,
        warnings=warnings,
    )

    assert len(anomalies_limited) <= 250
    assert len(cps_limited) <= 200
    assert len(causes_limited) <= 15
    assert len(ranked_limited) <= 15
    assert len(clusters_limited) <= 30
    assert len(granger_limited) <= 100
    assert warnings


def test_select_granger_series_filters_constant_and_short_series(monkeypatch):
    monkeypatch.setattr("config.settings.analyzer_granger_min_samples", 5)
    monkeypatch.setattr("config.settings.analyzer_granger_max_series", 2)
    selected = _select_granger_series(
        {
            "const": [1.0] * 10,
            "short": [1.0, 2.0, 3.0],
            "v1": [1.0, 3.0, 2.0, 5.0, 4.0, 7.0],
            "v2": [2.0, 5.0, 3.0, 9.0, 4.0, 12.0],
            "v3": [1.0, 8.0, 2.0, 7.0, 3.0, 6.0],
        }
    )
    assert "const" not in selected
    assert "short" not in selected
    assert len(selected) <= 2
