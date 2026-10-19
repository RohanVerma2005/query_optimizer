import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass
from typing import List
from config.database import get_connection

@dataclass
class RegressionAlert:
    digest_hash: str
    query_preview: str
    baseline_avg_ms: float
    recent_avg_ms: float
    percentage_change: float
    recent_executions: int
    status: str

def detect_regressions(recent_snapshots_count=3, threshold_pct=20.0, min_execs=1) -> List[RegressionAlert]:
    conn = get_connection(include_db=False)
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Fetch recent snapshot IDs to establish the boundary
        cursor.execute("""
            SELECT id FROM qpa_metrics.metric_snapshots 
            ORDER BY id DESC LIMIT %s
        """, (recent_snapshots_count,))
        recent_rows = cursor.fetchall()

        # Need at least 2 snapshot periods to detect a shift
        if not recent_rows or len(recent_rows) < 2:
            return []

        split_snapshot_id = min(r['id'] for r in recent_rows)

        # 2. Compare baseline window vs recent window
        query = """
        SELECT 
            c.digest_hash,
            SUBSTRING(c.digest_text, 1, 75) AS query_preview,
            COALESCE(SUM(IF(i.snapshot_id < %s, i.delta_exec_count, 0)), 0) AS base_execs,
            COALESCE(SUM(IF(i.snapshot_id < %s, i.delta_total_ms, 0.0)), 0.0) AS base_total_ms,
            COALESCE(SUM(IF(i.snapshot_id >= %s, i.delta_exec_count, 0)), 0) AS recent_execs,
            COALESCE(SUM(IF(i.snapshot_id >= %s, i.delta_total_ms, 0.0)), 0.0) AS recent_total_ms
        FROM qpa_metrics.query_interval_stats i
        JOIN qpa_metrics.query_catalog c ON i.digest_hash = c.digest_hash
        GROUP BY c.digest_hash, c.digest_text
        HAVING base_execs >= %s AND recent_execs >= %s;
        """

        cursor.execute(query, (
            split_snapshot_id,
            split_snapshot_id,
            split_snapshot_id,
            split_snapshot_id,
            min_execs,
            min_execs
        ))
        rows = cursor.fetchall()

        alerts: List[RegressionAlert] = []
        for r in rows:
            # Explicit float casting to resolve MySQL Decimal type incompatibilities
            base_count = float(r['base_execs'] or 0)
            recent_count = float(r['recent_execs'] or 0)

            if base_count == 0 or recent_count == 0:
                continue

            base_total = float(r['base_total_ms'] or 0.0)
            recent_total = float(r['recent_total_ms'] or 0.0)

            base_avg = base_total / base_count
            recent_avg = recent_total / recent_count

            if base_avg <= 0:
                continue

            pct_change = ((recent_avg - base_avg) / base_avg) * 100.0

            if pct_change >= threshold_pct:
                status = "CRITICAL" if pct_change >= 50.0 else "WARNING"
                alerts.append(RegressionAlert(
                    digest_hash=r['digest_hash'],
                    query_preview=r['query_preview'],
                    baseline_avg_ms=round(base_avg, 2),
                    recent_avg_ms=round(recent_avg, 2),
                    percentage_change=round(pct_change, 1),
                    recent_executions=int(recent_count),
                    status=status
                ))

        alerts.sort(key=lambda x: x.percentage_change, reverse=True)
        return alerts

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    from tabulate import tabulate
    alerts = detect_regressions()
    if alerts:
        table_data = [a.__dict__ for a in alerts]
        print(tabulate(table_data, headers="keys", tablefmt="fancy_grid"))
    else:
        print("No regressions detected (>20% threshold). Performance is stable.")