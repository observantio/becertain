"""
Constants and configuration for Be Certain.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import os
from typing import Dict, List, Tuple, Optional

from pydantic_settings import BaseSettings


REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BASELINE_TTL: int = int(os.getenv("BASELINE_TTL", "86400"))   
GRANGER_TTL: int = int(os.getenv("GRANGER_TTL", "604800")) 
EVENTS_TTL: int = int(os.getenv("EVENTS_TTL", "2592000"))  
WEIGHTS_TTL: int = int(os.getenv("WEIGHTS_TTL", "604800")) 
BLEND_ALPHA: float = float(os.getenv("BLEND_ALPHA", "0.1")) 

LOGS_BACKEND_LOKI = "loki"
METRICS_BACKEND_MIMIR = "mimir"
METRICS_BACKEND_VICTORIAMETRICS = "victoriametrics"
TRACES_BACKEND_TEMPO = "tempo"


BECERTAIN_LOGS_BACKEND = os.getenv("BECERTAIN_LOGS_BACKEND", LOGS_BACKEND_LOKI).lower()
BECERTAIN_LOGS_LOKI_URL = os.getenv("BECERTAIN_LOGS_LOKI_URL", "http://loki:3100").rstrip("/")
BECERTAIN_LOGS_LOKI_LABELS = os.getenv("BECERTAIN_LOGS_LOKI_LABELS", "")
BECERTAIN_LOGS_LOKI_TIMEOUT = int(os.getenv("BECERTAIN_LOGS_LOKI_TIMEOUT", "30"))
BECERTAIN_LOGS_LOKI_BATCH_SIZE = int(os.getenv("BECERTAIN_LOGS_LOKI_BATCH_SIZE", "1000"))

BECERTAIN_METRICS_BACKEND = os.getenv("BECERTAIN_METRICS_BACKEND", METRICS_BACKEND_MIMIR).lower()
BECERTAIN_METRICS_MIMIR_URL = os.getenv("BECERTAIN_METRICS_MIMIR_URL", "http://mimir:9009").rstrip("/")
BECERTAIN_METRICS_VICTORIAMETRICS_URL = os.getenv("BECERTAIN_METRICS_VICTORIAMETRICS_URL", "").rstrip("/")

BECERTAIN_TRACES_BACKEND = os.getenv("BECERTAIN_TRACES_BACKEND", TRACES_BACKEND_TEMPO).lower()
BECERTAIN_TRACES_TEMPO_URL = os.getenv("BECERTAIN_TRACES_TEMPO_URL", "http://tempo:3200").rstrip("/")

BECERTAIN_CONNECTOR_TIMEOUT = int(os.getenv("BECERTAIN_CONNECTOR_TIMEOUT", "30"))
BECERTAIN_STARTUP_TIMEOUT = int(os.getenv("BECERTAIN_STARTUP_TIMEOUT", "120"))

# tenant defaults
BECERTAIN_DEFAULT_TENANT_ID = os.getenv("BECERTAIN_DEFAULT_TENANT_ID", "Av45ZchZsQdKjN8XyG")


DEFAULT_SERVICE_NAME = "default_service"


SLO_ERROR_QUERY_TEMPLATE = (
    'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m]))'
)
SLO_TOTAL_QUERY_TEMPLATE = (
    'sum(rate(http_requests_total{{service="{service}"}}[5m]))'
)

# default metric queries used by various API routes when none are supplied
DEFAULT_METRIC_QUERIES = [
    "sum(rate(traces_spanmetrics_calls_total[5m])) by (service)",
    "histogram_quantile(0.99, sum(rate(traces_spanmetrics_latency_bucket[5m])) by (le, service))",
    "sum(rate(traces_spanmetrics_calls_total{status_code='STATUS_CODE_ERROR'}[5m])) by (service)",
    "sum(rate(traces_service_graph_request_failed_total[5m])) by (client, server)",
    "sum(rate(traces_service_graph_request_total[5m])) by (client, server)",
    "sum(rate(system_cpu_time_seconds_total[5m])) by (cpu)",
    "system_memory_usage_bytes",
    "system_filesystem_usage_bytes",
]

# explicit queries used by analyzer for SLO burn; kept separate from the
# configurable templates above because they target pre-aggregated spanmetrics
SLO_ERROR_QUERY = 'sum(rate(traces_spanmetrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))'
SLO_TOTAL_QUERY = 'sum(rate(traces_spanmetrics_calls_total[5m]))'

# thresholds for which metrics we attempt to forecast or signal degradation
FORECAST_THRESHOLDS: dict[str, float] = {
    "system_memory_usage_bytes": 0.85,
    "system_filesystem_usage_bytes": 0.90,
    "traces_spanmetrics_latency": 2.0,
    "traces_service_graph_request_failed": 0.05,
}

# weight values assigned to severity labels for comparison and ranking
SEVERITY_WEIGHTS: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 4,
    "critical": 8,
}

DATASOURCE_TIMEOUT = 30  
HEALTH_PATH = "/ready"

# registry defaults
DEFAULT_WEIGHTS: Dict[str, float] = {
    "metrics": 0.30,
    "logs": 0.35,
    "traces": 0.35,
}

REGISTRY_ALPHA: float = float(os.getenv("REGISTRY_ALPHA", "0.2")) 

class Settings(BaseSettings):
    logs_backend: str = BECERTAIN_LOGS_BACKEND
    loki_url: str = BECERTAIN_LOGS_LOKI_URL
    loki_labels: str = BECERTAIN_LOGS_LOKI_LABELS
    loki_timeout: int = BECERTAIN_LOGS_LOKI_TIMEOUT
    loki_batch_size: int = BECERTAIN_LOGS_LOKI_BATCH_SIZE

    metrics_backend: str = BECERTAIN_METRICS_BACKEND
    mimir_url: str = BECERTAIN_METRICS_MIMIR_URL
    victoriametrics_url: Optional[str] = (
        BECERTAIN_METRICS_VICTORIAMETRICS_URL or None
    )

    traces_backend: str = BECERTAIN_TRACES_BACKEND
    tempo_url: str = BECERTAIN_TRACES_TEMPO_URL

    connector_timeout: int = BECERTAIN_CONNECTOR_TIMEOUT
    startup_timeout: int = BECERTAIN_STARTUP_TIMEOUT

    slo_error_query_template: str = SLO_ERROR_QUERY_TEMPLATE
    slo_total_query_template: str = SLO_TOTAL_QUERY_TEMPLATE

    # default tenant (used by main and tests)
    default_tenant_id: str = BECERTAIN_DEFAULT_TENANT_ID

    mad_threshold: float = float(os.getenv("BECERTAIN_MAD_THRESHOLD", "3.5"))
    zscore_threshold: float = float(os.getenv("BECERTAIN_ZSCORE_THRESHOLD", "2.5"))
    cusum_threshold: float = float(os.getenv("BECERTAIN_CUSUM_THRESHOLD", "5.0"))
    min_samples: int = int(os.getenv("BECERTAIN_MIN_SAMPLES", "8"))

    burst_ratio_thresholds: List[Tuple[float, str]] = [
        (10.0, "critical"),
        (5.0, "high"),
        (2.5, "medium"),
    ]

    # severity score cutoffs used throughout the engine
    severity_score_critical: float = 0.75
    severity_score_high: float = 0.50
    severity_score_medium: float = 0.25

    # trace error propagation detection thresholds
    trace_error_rate_threshold: float = 0.05
    trace_error_severity_high: float = 0.10
    trace_error_severity_critical: float = 0.25

    # trace latency severity and apdex configuration
    trace_latency_p99_critical: float = 5000.0
    trace_latency_p99_high: float = 2000.0
    trace_latency_p99_medium: float = 500.0
    trace_latency_error_critical: float = 0.25
    trace_latency_error_high: float = 0.10
    trace_latency_error_medium: float = 0.02
    trace_latency_apdex_poor: float = 0.5
    trace_latency_apdex_marginal: float = 0.7
    trace_latency_apdex_t_ms: float = 500.0

    # baseline computation defaults
    baseline_zscore_threshold: float = 3.0
    baseline_min_samples: int = 6
    baseline_seasonal_min_samples: int = 24

    # changepoint detection
    cusum_window: int = 10
    cusum_relative_cutoff: float = 0.5
    # we keep legacy name for backwards compatibility but allow override
    cusum_threshold_sigma: float = cusum_threshold

    # correlation/temporal scoring
    max_lag_seconds: float = 120.0
    correlation_window_seconds: float = 60.0
    correlation_weight_time: float = 0.25
    correlation_weight_latency: float = 0.40
    correlation_weight_errors: float = 0.35
    correlation_score_max: float = 1.0
    correlation_errors_cap: float = 0.35

    # forecast degradation analysis
    forecast_min_degradation_rate: float = 0.01
    forecast_ema_alpha: float = 0.3
    forecast_degradation_threshold_critical: float = 0.3
    forecast_degradation_threshold_high: float = 0.15
    forecast_degradation_threshold_medium: float = 0.1
    forecast_degradation_min_length: int = 10

    # log pattern analysis constants
    logs_noise_regex: str = r"[0-9a-f]{8,}"
    logs_normalized_length_cutoff: int = 180
    logs_sample_snippet: int = 300
    logs_token_cap: int = 500
    logs_results_limit: int = 100
    logs_min_duration: float = 1.0

    # rca heuristics
    rca_window_seconds: float = 300.0
    rca_weights: Dict[str, float] = {"logs": 0.25, "latency": 0.40, "errors": 0.35}
    rca_deploy_score_cutoff: float = 0.6
    rca_errorprop_max: float = 0.95
    rca_baseline_base: float = 0.5
    rca_baseline_affected_factor: float = 0.1

    # analyzer tuning
    analyzer_sensitivity_factor: float = 0.67
    analyzer_max_parallel_metric_queries: int = 8
    analyzer_max_parallel_cpu_tasks: int = 4
    analyzer_granger_max_series: int = 20
    analyzer_granger_min_samples: int = 20

    # event registry window
    events_window_seconds: float = 300.0

    # Bayesian scoring priors/likelihoods
    # keys must correspond to the values of RcaCategory (e.g. "traffic_surge")
    bayesian_priors: Dict[str, float] = {
        "deployment": 0.35,
        "resource_exhaustion": 0.20,
        "dependency_failure": 0.20,
        "traffic_surge": 0.10,
        "error_propagation": 0.10,
        "slo_burn": 0.03,
        "unknown": 0.02,
    }
    bayesian_likelihoods: Dict[str, Dict[str, float]] = {
        "deployment": {
            "has_deployment_event": 0.95,
            "has_metric_spike":     0.70,
            "has_log_burst":        0.60,
            "has_latency_spike":    0.50,
            "has_error_propagation":0.40,
        },
        "resource_exhaustion": {
            "has_deployment_event": 0.15,
            "has_metric_spike":     0.90,
            "has_log_burst":        0.50,
            "has_latency_spike":    0.70,
            "has_error_propagation":0.30,
        },
        "dependency_failure": {
            "has_deployment_event": 0.10,
            "has_metric_spike":     0.50,
            "has_log_burst":        0.70,
            "has_latency_spike":    0.95,
            "has_error_propagation":0.80,
        },
        "traffic_surge": {
            "has_deployment_event": 0.05,
            "has_metric_spike":     0.95,
            "has_log_burst":        0.60,
            "has_latency_spike":    0.60,
            "has_error_propagation":0.20,
        },
        "error_propagation": {
            "has_deployment_event": 0.10,
            "has_metric_spike":     0.60,
            "has_log_burst":        0.80,
            "has_latency_spike":    0.85,
            "has_error_propagation":0.99,
        },
        "slo_burn": {
            "has_deployment_event": 0.20,
            "has_metric_spike":     0.80,
            "has_log_burst":        0.50,
            "has_latency_spike":    0.60,
            "has_error_propagation":0.50,
        },
        "unknown": {
            "has_deployment_event": 0.05,
            "has_metric_spike":     0.30,
            "has_log_burst":        0.30,
            "has_latency_spike":    0.30,
            "has_error_propagation":0.10,
        },
    }

    # causal graph defaults
    causal_graph_max_depth: int = 5
    causal_round_precision: int = 4

    # granger analysis defaults
    granger_max_lag: int = 3
    granger_p_threshold: float = 0.05
    granger_strength_scale: float = 10.0

    # forecast trajectory heuristics
    # minimum number of data points required before attempting a trajectory forecast
    forecast_trajectory_min_length: int = 8
    # minimum R² score for a linear fit to be considered usable
    forecast_trajectory_r2_threshold: float = 0.2
    forecast_trajectory_ratio_threshold: float = 0.5
    forecast_trajectory_window_seconds: float = 300.0
    forecast_trajectory_horizon_cutoff: float = 300.0

    # logs/frequency window
    logs_frequency_window_seconds: float = 10.0

    # deduplication
    dedup_time_window: float = 120.0

    # clustering defaults
    ml_cluster_eps: float = 0.1
    ml_cluster_min_samples: int = 2

    # RCA heuristics not covered earlier
    rca_event_confidence_threshold: float = 0.3
    rca_deploy_window_seconds: float = 300.0
    rca_score_cap: float = 0.99
    rca_slice_limit: int = 2
    rca_severity_weight_threshold: int = 3
    rca_log_pattern_score: float = 0.6

    # SLO burn windows: list of (label, window_seconds, threshold, severity)
    slo_burn_windows: List[Tuple[str, float, float, str]] = [
        ("1h", 3600, 14.4, "critical"),
        ("6h", 21600, 6.0, "high"),
        ("1d", 86400, 3.0, "medium"),
        ("3d", 259200, 1.0, "low"),
    ]

    # topology defaults
    topology_max_depth: int = 6

    # time window used for monthly SLO budgets (minutes)
    slo_month_minutes: float = 30 * 24 * 60
    slo_month_seconds: float = slo_month_minutes * 60
    slo_default_target_availability : float = 0.999

    # anomaly detection thresholds
    anomaly_z_thresholds: List[Tuple[float, float]] = [
        (4.0, 0.5),
        (3.0, 0.35),
        (2.5, 0.2),
    ]
    anomaly_mad_thresholds: List[Tuple[float, float]] = [
        (5.0, 0.35),
        (3.5, 0.25),
        (2.5, 0.15),
    ]
    anomaly_iso_weight: float = 0.15

    # anomaly detection defaults beyond thresholds
    anomaly_default_sensitivity: float = 3.0
    anomaly_percentile_low: float = 5.0
    anomaly_percentile_high: float = 95.0

    # cusum parameters used in changepoint detection
    cusum_k: float = 0.5
    cusum_oscillation_density_cutoff: float = 0.3

    # bayesian defaults
    bayesian_default_feature_prob: float = 0.5

    # additional knobs for anomaly detection
    anomaly_mad_scale: float = 0.6745
    anomaly_cusum_k: float = 0.5
    anomaly_drift_slope_threshold: float = 0.1
    anomaly_contamination_min: float = 0.01
    anomaly_contamination_max: float = 0.5
    anomaly_contamination_divisor: float = 0.5
    anomaly_min_sensitivity: float = 0.1
    anomaly_iso_n_estimators: int = 100
    anomaly_iso_random_state: int = 42

    # ML ranking configuration
    ranking_severity_divisor: float = 8.0
    ranking_signal_divisor: float = 10.0
    ranking_event_count_divisor: float = 5.0
    ranking_confidence_blend: float = 0.6
    ranking_ml_blend: float = 0.4
    ranking_rf_n_estimators: int = 50
    ranking_rf_max_depth: int = 4
    ranking_rf_random_state: int = 42
    ranking_label_threshold: float = 0.5

    # weights defaults
    default_weight_fallback: float = 0.0  # 0 means compute as 1/len(Signals) if not set
    store_redis_retry_cooldown_seconds: float = 10.0
    store_fallback_max_items: int = 10_000

    model_config = {
        "env_prefix": "BECERTAIN_",
        "extra": "ignore",
    }


settings = Settings()

