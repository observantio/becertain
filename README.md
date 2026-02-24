# 🧠 Be Certain

### The AI-Native Reasoning Engine for Infrastructure Observability.

**Be Certain** is a high-performance Python analytics engine designed to transform raw telemetry into actionable intelligence. By correlating metrics from **Mimir**, traces from **Tempo**, and logs from **Loki**, it provides deep-tier anomaly detection, predictive forecasting, and automated Root Cause Analysis (RCA).

![Worfklow of Be Certain](assets/beobservant.png)

Built with a modular, "drop-in" architecture, Be Certain allows SRE teams to utilize pre-built analysis modules or extend the engine with custom logic for specific domain needs.

---

## 🚀 Key Features

> **Note:** Be Certain is currently in active development. We are refining our ML models and welcome PRs to help stabilize core heuristics.

* 🧠 **Multi-Dimensional Anomaly Detection:** Detect silent failures using advanced time-series pattern recognition.
* 📈 **Intelligent Forecasting:** Move from reactive to proactive with predictive trajectory models and baseline bands.
* 🔗 **Causal Correlation:** Understand the *why* by linking disparate events across logs and traces.
* 📊 **SLO-Centric Monitoring:** Automate error-budget burn rate calculations and availability targets.
* 🔌 **Plug-and-Play Connectors:** Native support for the LGTM stack (Loki, Grafana, Tempo, Mimir) and VictoriaMetrics.
* 🧪 **Developer First:** Modular internal packages and a comprehensive `pytest` suite for reliable extensibility.

---

## ⚙️ The Analysis Pipeline

The heart of Be Certain is the `POST /api/v1/analyze` endpoint. It orchestrates a staged pipeline that moves from raw data ingestion to high-level hypothesis ranking.

| Stage | Responsibility | Logic |
| --- | --- | --- |
| **Orchestration** | `analyzer.py` | The "Conductor." Manages the workflow from fetch to final report. |
| **Ingestion** | `fetcher.py` | High-concurrency data retrieval with smart fallback mechanisms. |
| **Detection** | `anomaly/*` | Identifies structural shifts and classifies severity in real-time. |
| **Context** | `baseline/*` | Computes dynamic Z-score bands to interpret normal vs. abnormal behavior. |
| **Shifts** | `changepoint/*` | Uses CUSUM logic to detect sudden oscillations or permanent shifts. |
| **Signals** | `logs/*` & `traces/*` | Extracts log patterns and maps latency degradation across service spans. |
| **Logic** | `correlation/*` | Temporally aligns anomalies to find "clumps" of evidence. |
| **Causality** | `causal/*` | Applies Granger-causality and Bayesian posteriors to find the source. |
| **Hypothesis** | `rca/*` | Ranks likely root causes based on evidence weights and topology. |
| **Topology** | `topology/*` | Maps the "Blast Radius" and upstream dependencies of a failure. |

---

## 🛠️ Project Architecture

Be Certain is structured to be "import-friendly." Whether you are running the full API or just using the `engine` as a library, the structure is clean and predictable.

```text
.
├── api/                # FastAPI routes and Pydantic schemas
├── connectors/         # Client wrappers for Loki, Mimir, Tempo
├── datasources/        # Abstraction layer for multi-source data fetching
├── engine/             # The "Brain" - individual analysis modules
│   ├── anomaly/        # Detection heuristics
│   ├── causal/         # Bayesian & Granger logic
│   ├── ml/             # Clustering and scoring weights
│   └── rca/            # Root cause ranking
├── store/              # Persistence layer for results and baselines
└── tests/              # Exhaustive component & integration tests
```

---

## 📦 Getting Started

### 1. Installation

Clone the repository into your workspace:

```bash
git clone https://github.com/observantio/becertain.git BeCertain
cd BeCertain
```

### 2. Run with Docker

The easiest way to get started is using the provided Dockerfile:

```bash
docker build -t becertain:latest .
docker run --rm -it -p 8000:8000 --name becertain becertain:latest
```

### 3. Local Development

For local testing or debugging individual modules:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

---

## 🤝 Contributing

We love contributors! Whether it's a new causal algorithm or a bug fix in the OTel fetcher, your help is appreciated.

**Developer Checklist:**

1. Create a feature branch.
2. Ensure all tests pass: `pytest -q`.
3. Ensure your `pre-commit` hooks are active.

---

## 📄 License

Licensed under the **Apache License 2.0**. You are free to use, modify, and distribute this software, provided that all original attribution notices are preserved.

*Disclaimer: This software is provided "as is" without warranty. The maintainers are not affiliated with third-party service providers mentioned in the connectors.*

