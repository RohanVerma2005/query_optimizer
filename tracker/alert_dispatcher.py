import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from analyzer.regression_detector import detect_regressions

def dispatch_alerts():
    alerts = detect_regressions(recent_snapshots_count=3, threshold_pct=20.0)
    if not alerts:
        return

    print("\n" + "!" * 60)
    print(" [ALERT DISPATCHER] ACTIVE REGRESSIONS DETECTED")
    print("!" * 60)
    for a in alerts:
        print(f"[{a.status}] Query: {a.query_preview[:60]}...")
        print(f"         Baseline: {a.baseline_avg_ms}ms -> Recent: {a.recent_avg_ms}ms (+{a.percentage_change}%)")
    print("!" * 60 + "\n")

if __name__ == "__main__":
    dispatch_alerts()