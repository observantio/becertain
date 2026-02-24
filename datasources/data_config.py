"""
Data source connectors for querying traces, metrics, and logs from various backends

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings
from config import (
    LOGS_BACKEND_LOKI,
    METRICS_BACKEND_MIMIR,
    METRICS_BACKEND_VICTORIAMETRICS,
    TRACES_BACKEND_TEMPO,
    BECERTAIN_LOGS_BACKEND,
    BECERTAIN_LOGS_LOKI_URL,
    BECERTAIN_LOGS_LOKI_LABELS,
    BECERTAIN_LOGS_LOKI_TIMEOUT,
    BECERTAIN_LOGS_LOKI_BATCH_SIZE,
    BECERTAIN_METRICS_BACKEND,
    BECERTAIN_METRICS_MIMIR_URL,
    BECERTAIN_METRICS_VICTORIAMETRICS_URL,
    BECERTAIN_TRACES_BACKEND,
    BECERTAIN_TRACES_TEMPO_URL,
    BECERTAIN_CONNECTOR_TIMEOUT,
    BECERTAIN_STARTUP_TIMEOUT,
)

class DataSourceSettings(BaseSettings):
    logs_backend: str = BECERTAIN_LOGS_BACKEND
    metrics_backend: str = BECERTAIN_METRICS_BACKEND
    traces_backend: str = BECERTAIN_TRACES_BACKEND
    loki_url: str = BECERTAIN_LOGS_LOKI_URL
    mimir_url: str = BECERTAIN_METRICS_MIMIR_URL
    tempo_url: str = BECERTAIN_TRACES_TEMPO_URL
    victoriametrics_url: Optional[str] = BECERTAIN_METRICS_VICTORIAMETRICS_URL
    connector_timeout: int = BECERTAIN_CONNECTOR_TIMEOUT
    startup_timeout: int = BECERTAIN_STARTUP_TIMEOUT
    @field_validator("loki_url", "mimir_url", "tempo_url", "victoriametrics_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: Optional[str]) -> Optional[str]:
        return str(v).rstrip("/") if v is not None else v

    @field_validator("logs_backend", mode="before")
    @classmethod
    def validate_logs_backend(cls, v: str) -> str:
        value = str(v or "").strip().lower()
        if value not in {LOGS_BACKEND_LOKI}:
            raise ValueError(f"Unsupported logs backend: {value!r}")
        return value

    @field_validator("metrics_backend", mode="before")
    @classmethod
    def validate_metrics_backend(cls, v: str) -> str:
        value = str(v or "").strip().lower()
        if value not in {METRICS_BACKEND_MIMIR, METRICS_BACKEND_VICTORIAMETRICS}:
            raise ValueError(f"Unsupported metrics backend: {value!r}")
        return value

    @field_validator("traces_backend", mode="before")
    @classmethod
    def validate_traces_backend(cls, v: str) -> str:
        value = str(v or "").strip().lower()
        if value not in {TRACES_BACKEND_TEMPO}:
            raise ValueError(f"Unsupported traces backend: {value!r}")
        return value

    model_config = {"env_prefix": "BECERTAIN_", "extra": "ignore"}
