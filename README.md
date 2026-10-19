#  Query Performance Analyzer & Auto-Optimizer (QPA)

A local telemetry, diagnostics, and auto-optimization suite for MySQL built in Python, PyCharm, and DataGrip.

---

## System Architecture
┌──────────────────────────────────────────────┐
│             MySQL Target Database            │
│     (performance_schema & sys schema)        │
└───────────────────────┬──────────────────────┘
│ 1. Poll Statement Digests (Monotonic Counters)
                        ▼
┌──────────────────────────────────────────────┐
│          Python Collector Daemon             │
│   - APScheduler (Periodic Snapshots)         │
│   - DeltaCalculator (Handles MySQL Resets)   │
└───────────────────────┬──────────────────────┘
│ 2. Persist Interval Deltas
                        ▼
┌──────────────────────────────────────────────┐
│           qpa_metrics Storage DB             │
│  (query_catalog, snapshots, interval_stats)  │
└───────────────────────┬──────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌────────────────────────┐      ┌────────────────────────┐
│   Analytical Engine    │      │ AST & Optimizer Engine │
│ - Top-N Resource Hogs  │      │ - sqlglot AST Parser   │
│ - Regression Detector  │      │ - ESR Index Heuristic  │
│ - Alert Dispatcher     │      │ - Invisible Index Test │
└───────────────┬────────┘      │ - Rule Query Rewriter  │
│               └───────────┬────────────┘
              ▼                           ▼
┌────────────────────────────────────────────────────────┐
│               Presentation Layer                       │
│   - Terminal CLI Diagnostic Suite (tabulate)           │
│   - Real-Time Interactive Streamlit Dashboard          │
└────────────────────────────────────────────────────────┘

---

## Quickstart & Setup

### 1. Requirements & Prerequisites
- Python 3.10+
- MySQL Server 8.0+ (with `performance_schema` enabled)
- JetBrains DataGrip & PyCharm

### 2. Environment Setup
```bash
git clone <repo_url>
cd query-performance-analyzer
python -m venv .venv

# On Windows:
.venv\Scripts\activate

pip install -r requirements.txt

3. Database Initialization

3.1.Configure connection settings in .env:

Code snippet
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=qpa_workload
METRICS_DB_NAME=qpa_metrics

3.2.In DataGrip, execute:

scripts/schema.sql (Creates 6 tables: customers, orders, order_items, products, categories, reviews).

collector/metrics_schema.sql (Creates metrics catalog and snapshots store).

tracker/schema_tracking.sql (Creates before/after optimization ledger).

3.3.Seed 10,000 realistic rows per table:

python scripts/seed_data.py


Running the SystemAutomated End-to-End DemoTo run the complete pipeline (workload-> capture -> regression simulation -> report):

python scripts/run_demo.py

Open http://localhost:8501 to view real-time latency trends, top offenders, active regressions, and validated index proposals.

pytest -v








