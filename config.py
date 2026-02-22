"""
Constants and configuration for Be Certain.

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import os
from typing import List, Tuple, Optional

from pydantic_settings import BaseSettings


REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BASELINE_TTL: int = int(os.getenv("BASELINE_TTL", "86400"))   
GRANGER_TTL: int = int(os.getenv("GRANGER_TTL", "604800")) 
EVENTS_TTL: int = int(os.getenv("EVENTS_TTL", "2592000"))  
WEIGHTS_TTL: int = int(os.getenv("WEIGHTS_TTL", "604800"))  # one week by default

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

    # slo query templates; can be overridden via BECERTAIN_SLO_ERROR_QUERY_TEMPLATE
    # and BECERTAIN_SLO_TOTAL_QUERY_TEMPLATE environment vars
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

    class Config:
        env_prefix = "BECERTAIN_"
        extra = "ignore"


settings = Settings()


