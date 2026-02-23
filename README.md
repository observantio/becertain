# Be Certain

**Be Certain** is a Python‑based analytics platform for ingesting, processing and correlating telemetry from diverse sources. Its modular architecture separates APIs, connectors, data sources, engines and persistence layers to promote extensibility and maintainability.

### 🚀 Core Capabilities

- **Anomaly Detection** – multiple algorithms for identifying irregularities in time‑series data  
- **Forecasting & Baselines** – predictive models and baseline computations  
- **Correlation & Causal Analysis** – tools to explore relationships between metrics and events  
- **SLO Monitoring** – query templates and endpoints to calculate service‑level objectives  
- **Connectors** – built‑in support for Loki, Mimir, Tempo and Victoria stores  
- **Persistent Storage** – registry and client modules for results and configuration  
- **Comprehensive Testing** – pytest suite covering all components

### 🛠️ Project Layout

```
.
├── Dockerfile
├── LICENSE
├── README.md
├── api
│   ├── __init__.py
│   ├── requests
│   │   └── __init__.py
│   ├── responses
│   │   └── __init__.py
│   └── routes
│       ├── __init__.py
│       ├── analyze.py
│       ├── causal.py
│       ├── common.py
│       ├── correlation.py
│       ├── events.py
│       ├── exception.py
│       ├── forecast.py
│       ├── health.py
│       ├── logs.py
│       ├── metrics.py
│       ├── ml.py
│       ├── slo.py
│       ├── topology.py
│       └── traces.py
├── config.py
├── connectors
│   ├── __init__.py
│   ├── loki.py
│   ├── mimir.py
│   ├── tempo.py
│   └── victoria.py
├── datasources
│   ├── __init__.py
│   ├── base.py
│   ├── data_config.py
│   ├── exceptions.py
│   ├── factory.py
│   ├── helpers.py
│   ├── provider.py
│   └── retry.py
├── engine
│   ├── __init__.py
│   ├── analyzer.py
│   ├── anomaly
│   │   ├── __init__.py
│   │   ├── detection.py
│   │   └── series.py
│   ├── baseline
│   │   ├── __init__.py
│   │   └── compute.py
│   ├── causal
│   │   ├── __init__.py
│   │   ├── bayesian.py
│   │   ├── granger.py
│   │   └── graph.py
│   ├── changepoint
│   │   ├── __init__.py
│   │   └── cusum.py
│   ├── constants.py
│   ├── correlation
│   │   ├── __init__.py
│   │   ├── signals.py
│   │   └── temporal.py
│   ├── dedup
│   │   ├── __init__.py
│   │   └── grouping.py
│   ├── enums.py
│   ├── events
│   │   ├── __init__.py
│   │   └── registry.py
│   ├── fetcher.py
│   ├── forecast
│   │   ├── __init__.py
│   │   ├── degradation.py
│   │   └── trajectory.py
│   ├── logs
│   │   ├── __init__.py
│   │   ├── frequency.py
│   │   └── patterns.py
│   ├── ml
│   │   ├── __init__.py
│   │   ├── clustering.py
│   │   ├── ranking.py
│   │   └── weights.py
│   ├── rca
│   │   ├── __init__.py
│   │   ├── hypothesis.py
│   │   └── scoring.py
│   ├── registry.py
│   ├── slo
│   │   ├── __init__.py
│   │   ├── budget.py
│   │   └── burn.py
│   ├── topology
│   │   ├── __init__.py
│   │   └── graph.py
│   └── traces
│       ├── __init__.py
│       ├── errors.py
│       └── latency.py
├── main.py
├── pytest.ini
├── requirements.txt
├── run.py
├── store
│   ├── __init__.py
│   ├── baseline.py
│   ├── client.py
│   ├── events.py
│   ├── granger.py
│   ├── keys.py
│   ├── registry.py
│   └── weights.py
└── tests
    ├── conftest.py
    ├── test_anomaly_detection.py
    ├── test_api_models.py
    ├── test_api_routes_events.py
    ├── test_api_routes_slo.py
    ├── test_correlation.py
    ├── test_degradation.py
    ├── test_engine_causal.py
    ├── test_engine_weights.py
    ├── test_enums.py
    ├── test_events_registry.py
    ├── test_fetcher.py
    ├── test_forecast.py
    ├── test_fuzzy.py
    ├── test_helpers.py
    ├── test_logs.py
    ├── test_rca_hypothesis.py
    ├── test_retry.py
    ├── test_slo.py
    ├── test_store_baseline.py
    ├── test_store_client.py
    ├── test_store_granger.py
    ├── test_store_keys.py
    ├── test_store_registry.py
    ├── test_store_weights.py
    └── test_topology.py
```

## 📦 Installation

```bash
git clone https://github.com/StefanKumarasinghe/becertain.git
cd becertain
```

## ⚙️ Usage

Run the main application with Docker:

```bash
docker build -t becertain:latest .

docker run --rm -it \
    -p 8000:8000 \
    --name becertain \
    becertain:latest
```

or execute individual modules for development and debugging.

## 🧩 Contributing

Contributions are welcome! Please follow standard GitHub workflow with feature branches and pull requests. Ensure tests pass:

```bash
pytest -q
```

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE).

---

> _Clean, professional analytics for confident decision-making._ Powering Be Observant (To be released)