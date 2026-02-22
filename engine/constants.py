from __future__ import annotations

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

SLO_ERROR_QUERY = 'sum(rate(traces_spanmetrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))'
SLO_TOTAL_QUERY = 'sum(rate(traces_spanmetrics_calls_total[5m]))'

FORECAST_THRESHOLDS: dict[str, float] = {
    "system_memory_usage_bytes": 0.85,
    "system_filesystem_usage_bytes": 0.90,
    "traces_spanmetrics_latency": 2.0,
    "traces_service_graph_request_failed": 0.05,
}