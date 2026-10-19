import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure root .env is loaded
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

class Settings:
    # Target & Telemetry Databases
    TARGET_SCHEMA: str = os.getenv("DB_NAME", "qpa_workload")
    METRICS_SCHEMA: str = os.getenv("METRICS_DB_NAME", "qpa_metrics")

    # Collector Engine Settings
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", 10))

    # Regression Detection Engine
    REGRESSION_THRESHOLD_PCT: float = float(os.getenv("REGRESSION_THRESHOLD_PCT", 20.0))
    REGRESSION_RECENT_WINDOW: int = int(os.getenv("REGRESSION_RECENT_WINDOW", 3))
    REGRESSION_MIN_EXECUTIONS: int = int(os.getenv("REGRESSION_MIN_EXECUTIONS", 2))

    # Explain & Analysis Thresholds
    FULL_SCAN_SEVERITY_THRESHOLD: int = 1000
    INEFFICIENCY_RATIO_THRESHOLD: float = 10.0

    # Safety Guardrails
    ALLOW_AUTO_APPLY_DDL: bool = False  # NEVER auto-execute DDL on production workloads

settings = Settings()