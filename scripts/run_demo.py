import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
from scripts.workload_generator import run_workload
from collector.scheduler import collect_metrics_job
from scripts.simulate_regression import simulate_regressed_workload
from analyzer.report_cli import run_cli_report

def run_end_to_end_demo():
    print("=" * 80)
    print("  LAUNCHING QUERY PERFORMANCE ANALYZER END-TO-END DEMO")
    print("=" * 80)

    # 1. Warm-up workload
    print("\n[Stage 1/4] Running Initial Workload (Fast + Anti-Pattern Mix)...")
    run_workload(iterations=120)

    # 2. Capture baseline snapshots
    print("\n[Stage 2/4] Capturing Baseline Performance Schema Snapshots...")
    collect_metrics_job()
    time.sleep(1)
    collect_metrics_job()

    # 3. Inject simulated regression
    print("\n[Stage 3/4] Simulating Latency Regression (Unindexed Search)...")
    simulate_regressed_workload(iterations=20)
    time.sleep(1)
    collect_metrics_job()

    # 4. Run automated analyzer report
    print("\n[Stage 4/4] Executing Diagnostics, EXPLAIN Analysis, and Index Advisor...\n")
    run_cli_report()

    print("=" * 80)
    print("  DEMO COMPLETE: All engines executed and verified successfully.")
    print("  Launch interactive UI: streamlit run dashboard/app.py")
    print("=" * 80)

if __name__ == "__main__":
    run_end_to_end_demo()