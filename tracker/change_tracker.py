import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.database import get_connection

class ChangeTracker:
    def __init__(self):
        pass

    def record_applied_optimization(self, digest_hash: str, opt_type: str, details: str):
        """
        Calculates baseline performance for the digest and logs an applied change.
        """
        conn = get_connection(include_db=False)
        cursor = conn.cursor(dictionary=True)

        try:
            # 1. Fetch current baseline performance before the change
            cursor.execute("""
                SELECT 
                    ROUND(SUM(delta_total_ms) / NULLIF(SUM(delta_exec_count), 0), 2) AS avg_ms,
                    ROUND(SUM(delta_rows_examined) / NULLIF(SUM(delta_exec_count), 0), 0) AS avg_scanned
                FROM qpa_metrics.query_interval_stats
                WHERE digest_hash = %s;
            """, (digest_hash,))
            row = cursor.fetchone()
            before_ms = float(row['avg_ms'] or 0.0)
            before_scanned = float(row['avg_scanned'] or 0.0)

            # 2. Insert record
            cursor.execute("""
                INSERT INTO qpa_metrics.applied_optimizations 
                (digest_hash, optimization_type, details, before_avg_latency_ms, before_avg_rows_scanned)
                VALUES (%s, %s, %s, %s, %s);
            """, (digest_hash, opt_type, details, before_ms, before_scanned))
            conn.commit()
            print(f"Recorded {opt_type} application for {digest_hash[:16]}... (Baseline: {before_ms}ms)")
        finally:
            cursor.close()
            conn.close()

    def update_after_metrics(self, optimization_id: int):
        """
        Calculates post-optimization metrics based on intervals captured after applied_at.
        """
        conn = get_connection(include_db=False)
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("SELECT * FROM qpa_metrics.applied_optimizations WHERE id = %s", (optimization_id,))
            opt = cursor.fetchone()
            if not opt:
                return

            # Compute metrics from intervals after the change timestamp
            cursor.execute("""
                SELECT 
                    ROUND(SUM(i.delta_total_ms) / NULLIF(SUM(i.delta_exec_count), 0), 2) AS after_ms,
                    ROUND(SUM(i.delta_rows_examined) / NULLIF(SUM(i.delta_exec_count), 0), 0) AS after_scanned
                FROM qpa_metrics.query_interval_stats i
                JOIN qpa_metrics.metric_snapshots s ON i.snapshot_id = s.id
                WHERE i.digest_hash = %s AND s.captured_at > %s;
            """, (opt['digest_hash'], opt['applied_at']))
            after_row = cursor.fetchone()

            if after_row and after_row['after_ms'] is not None:
                after_ms = float(after_row['after_ms'])
                after_scanned = float(after_row['after_scanned'])
                before_ms = float(opt['before_avg_latency_ms'])

                improvement = 0.0
                if before_ms > 0:
                    improvement = round(((before_ms - after_ms) / before_ms) * 100.0, 1)

                cursor.execute("""
                    UPDATE qpa_metrics.applied_optimizations 
                    SET after_avg_latency_ms = %s,
                        after_avg_rows_scanned = %s,
                        improvement_pct = %s
                    WHERE id = %s;
                """, (after_ms, after_scanned, improvement, optimization_id))
                conn.commit()
                print(f"Updated Optimization #{optimization_id}: {before_ms}ms -> {after_ms}ms ({improvement}% improvement)")
        finally:
            cursor.close()
            conn.close()