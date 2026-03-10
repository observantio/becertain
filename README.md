# Be Certain

Be Certain is the internal analysis engine in the Observantio platform. It takes logs, metrics, and traces from the configured backends, runs anomaly and correlation logic across them, and returns RCA-oriented results that can be consumed synchronously or as background jobs.

This service is not a generic dashboard backend. Its job is to answer questions like: what changed, where did it start, what correlated with it, what is the likely blast radius, and what does the evidence suggest as the most probable root cause.

![Workflow of Be Certain](assets/beobservant.png)

## What This Service Does

- Runs full cross-signal RCA over logs, metrics, and traces.
- Exposes focused APIs for metrics, logs, traces, correlation, causality, SLOs, forecasting, topology, events, and ML helpers.
- Supports both immediate analysis and persisted asynchronous job execution.
- Waits for configured observability backends to become reachable during startup.
- Optionally persists RCA jobs and reports when `BECERTAIN_DATABASE_URL` is configured.

## Runtime Overview

| Detail | Value |
| --- | --- |
| Service name | `BeCertain` |
| Default host | `127.0.0.1` |
| Default port | `4322` |
| Main API prefix | `/api/v1` |
| Health | `/api/v1/health` |
| Readiness | `/api/v1/ready` |
| Default logs backend | Loki |
| Default metrics backend | Mimir |
| Default traces backend | Tempo |

Startup behavior:

- The service boots the FastAPI app.
- If `BECERTAIN_DATABASE_URL` is set, it initializes the database and job store.
- It performs backend readiness checks for the configured logs, metrics, and traces systems.
- It starts a background cleanup loop for report retention when the database-backed job service is enabled.

## Security Model

Be Certain is designed for internal service-to-service use.

Requests are protected by `InternalAuthMiddleware` and internal permission checks. In practice, the caller must provide:

- a valid shared service token via `BECERTAIN_EXPECTED_SERVICE_TOKEN`
- a valid internal context token signed with the configured context key
- permissions such as `create:rca`, `read:rca`, or `delete:rca` for the relevant route

Important settings:

```env
BECERTAIN_EXPECTED_SERVICE_TOKEN=replace-with-a-long-random-shared-secret
BECERTAIN_CONTEXT_VERIFY_KEY=replace-with-shared-context-key
BECERTAIN_CONTEXT_ISSUER=beobservant-main
BECERTAIN_CONTEXT_AUDIENCE=becertain
BECERTAIN_CONTEXT_ALGORITHMS=HS256
BECERTAIN_CONTEXT_REPLAY_TTL_SECONDS=180
```

## API Surface

The service exposes a broader analysis API than the old README described.

Major route groups under `/api/v1`:

- `POST /analyze`: synchronous full RCA.
- `POST /jobs/analyze`: enqueue asynchronous RCA.
- `GET /jobs`, `GET /jobs/{job_id}`, `GET /jobs/{job_id}/result`: inspect jobs and results.
- `GET /reports/{report_id}`, `DELETE /reports/{report_id}`: persisted report retrieval and deletion.
- Health, metrics, logs, traces, correlation, causal, forecast, events, topology, SLO, and ML helper endpoints.

The route tree is assembled from:

- `api/routes/analyze.py`
- `api/routes/jobs.py`
- `api/routes/metrics.py`
- `api/routes/logs.py`
- `api/routes/traces.py`
- `api/routes/correlation.py`
- `api/routes/causal.py`
- `api/routes/forecast.py`
- `api/routes/events.py`
- `api/routes/topology.py`
- `api/routes/slo.py`
- `api/routes/ml.py`

## Analysis Model

Be Certain combines several layers of reasoning rather than relying on a single detector.

| Layer | Purpose |
| --- | --- |
| Fetch and datasource routing | Collects signals from Loki, Mimir, Tempo, or VictoriaMetrics |
| Anomaly detection | Flags unusual changes in time series and derived signals |
| Baselines and changepoints | Separates structural change from normal variation |
| Correlation | Aligns multi-signal evidence over time |
| Causal analysis | Ranks candidate sources using causal and heuristic logic |
| RCA synthesis | Produces an operator-readable report or job result |
| Forecasting and SLO logic | Adds risk and burn-rate context to the analysis |

This is why the service is useful both for on-demand RCA and for background analysis jobs tied to incidents or operational workflows.

## Backends and Connectors

Supported defaults in the current configuration:

- Logs: Loki
- Metrics: Mimir or VictoriaMetrics
- Traces: Tempo

Default URLs:

```env
BECERTAIN_LOGS_LOKI_URL=http://loki:3100
BECERTAIN_METRICS_MIMIR_URL=http://mimir:9009
BECERTAIN_TRACES_TEMPO_URL=http://tempo:3200
```

These are probed during startup. If a backend does not become ready within `BECERTAIN_STARTUP_TIMEOUT`, readiness stays degraded and the service logs which backend failed.

## Environment Variables

The complete configuration surface is in `config.py`. The following variables are the most important for developers and operators.

### Core Runtime

```env
BECERTAIN_HOST=127.0.0.1
BECERTAIN_PORT=4322
BECERTAIN_CONNECTOR_TIMEOUT=10
BECERTAIN_STARTUP_TIMEOUT=120
```

### Backend Selection

```env
BECERTAIN_LOGS_BACKEND=loki
BECERTAIN_METRICS_BACKEND=mimir
BECERTAIN_TRACES_BACKEND=tempo
```

### Backend URLs

```env
BECERTAIN_LOGS_LOKI_URL=http://loki:3100
BECERTAIN_METRICS_MIMIR_URL=http://mimir:9009
BECERTAIN_METRICS_VICTORIAMETRICS_URL=
BECERTAIN_TRACES_TEMPO_URL=http://tempo:3200
```

### Job and Database Settings

```env
BECERTAIN_DATABASE_URL=postgresql://user:strongPassword@db:5432/observantio
BECERTAIN_ANALYZE_MAX_CONCURRENCY=2
BECERTAIN_ANALYZE_TIMEOUT_SECONDS=90
BECERTAIN_ANALYZE_REPORT_RETENTION_DAYS=7
BECERTAIN_ANALYZE_JOB_TTL_DAYS=30
```

### Security Settings

```env
BECERTAIN_EXPECTED_SERVICE_TOKEN=replace-with-a-long-random-shared-secret
BECERTAIN_CONTEXT_VERIFY_KEY=replace-with-shared-context-key
BECERTAIN_CONTEXT_ISSUER=beobservant-main
BECERTAIN_CONTEXT_AUDIENCE=becertain
BECERTAIN_CONTEXT_ALGORITHMS=HS256
```

### Optional TLS

```env
BECERTAIN_SSL_ENABLED=false
BECERTAIN_SSL_CERTFILE=
BECERTAIN_SSL_KEYFILE=
```

## Local Development

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

At minimum, set backend URLs and internal auth secrets. If you want async job persistence, set `BECERTAIN_DATABASE_URL` as well.

### 3. Run the service

```bash
python main.py
```

Or with uvicorn:

```bash
uvicorn main:app --host 127.0.0.1 --port 4322 --reload
```

### 4. Run tests

```bash
pytest -q
```

## Docker

Build and run locally:

```bash
docker build -t becertain:latest .
docker run --rm -it \
	-p 4322:4322 \
	--env-file .env \
	--name becertain \
	becertain:latest
```

For multi-service development, prefer the root mono-repo `docker-compose.yml` and shared environment configuration.

## Developer Notes

- `main.py` owns startup, backend readiness, and optional DB-backed job recovery.
- `api/routes/analyze.py` is the synchronous RCA entry point.
- `api/routes/jobs.py` exposes the async job lifecycle and persisted report APIs.
- `datasources/` abstracts the configured backends.
- `engine/` contains the detection, correlation, causal, RCA, and topology logic.
- `store/` contains caching and persistence helpers used by the analysis engine.

## Troubleshooting

Common issues:

- `/api/v1/ready` returns `503`: one or more configured backends did not pass readiness checks.
- job APIs fail unexpectedly: `BECERTAIN_DATABASE_URL` is missing or database initialization failed.
- internal auth fails: the service token or context key does not match the caller configuration.
- analysis quality looks weak: verify that the selected backend URLs and tenant headers are aligned with your data source layout.

## License

Licensed under the Apache License 2.0.

Preserve the existing attribution and notice headers in redistributed copies.

