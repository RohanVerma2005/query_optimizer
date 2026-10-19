import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import time
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from config.database import get_connection
from collector.delta_calculator import DeltaCalculator, RawDigestMetric

TARGET_SCHEMA = os.getenv("DB_NAME", "qpa_workload")
POLL_INTERVAL_SECONDS = 10

calculator = DeltaCalculator()

def get_server_uptime(cursor) -> int:
    cursor.execute("SHOW GLOBAL STATUS LIKE 'Uptime'")
    row = cursor.fetchone()
    return int(row[1]) if row else 0

def fetch_current_digests(cursor) -> dict[str, RawDigestMetric]:
    query = """
    SELECT 
        DIGEST AS digest_hash,
        SCHEMA_NAME AS schema_name,
        DIGEST_TEXT AS digest_text,
        COUNT_STAR AS count_star,
        ROUND(SUM_TIMER_WAIT / 1000000000, 3) AS sum_timer_wait_ms,
        SUM_ROWS_EXAMINED AS sum_rows_examined,
        SUM_ROWS_SENT AS sum_rows_sent
    FROM performance_schema.events_statements_summary_by_digest
    WHERE SCHEMA_NAME = %s AND DIGEST IS NOT NULL
    """
    cursor.execute(query, (TARGET_SCHEMA,))
    rows = cursor.fetchall()

    metrics = {}
    for r in rows:
        d_hash = r[0]
        metrics[d_hash] = RawDigestMetric(
            digest_hash=d_hash,
            schema_name=r[1],
            digest_text=r[2],
            count_star=r[3],
            sum_timer_wait_ms=float(r[4]),
            sum_rows_examined=int(r[5]),
            sum_rows_sent=int(r[6])
        )
    return metrics

def persist_snapshot(conn, metrics: dict[str, RawDigestMetric], deltas: list):
    cursor = conn.cursor()
    try:
        # 1. Upsert new query fingerprints into catalog
        catalog_query = """
        INSERT INTO qpa_metrics.query_catalog (digest_hash, schema_name, digest_text)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            digest_text = VALUES(digest_text),
            last_seen = CURRENT_TIMESTAMP
        """
        catalog_data = [
            (m.digest_hash, m.schema_name, m.digest_text)
            for m in metrics.values()
        ]
        if catalog_data:
            cursor.executemany(catalog_query, catalog_data)

        # 2. Record the snapshot entry
        uptime = get_server_uptime(cursor)
        cursor.execute(
            "INSERT INTO qpa_metrics.metric_snapshots (server_uptime_sec) VALUES (%s)",
            (uptime,)
        )
        snapshot_id = cursor.lastrowid

        # 3. Store query interval deltas
        if deltas:
            stats_query = """
            INSERT INTO qpa_metrics.query_interval_stats (
                snapshot_id, digest_hash, interval_seconds,
                delta_exec_count, delta_total_ms, avg_latency_ms,
                delta_rows_examined, delta_rows_sent, examined_to_sent_ratio
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            stats_data = [
                (
                    snapshot_id,
                    d.digest_hash,
                    POLL_INTERVAL_SECONDS,
                    d.delta_exec_count,
                    d.delta_total_ms,
                    d.avg_latency_ms,
                    d.delta_rows_examined,
                    d.delta_rows_sent,
                    d.examined_to_sent_ratio
                )
                for d in deltas
            ]
            cursor.executemany(stats_query, stats_data)

        conn.commit()
        return snapshot_id, len(deltas)
    finally:
        cursor.close()

def collect_metrics_job():
    conn = get_connection(include_db=False)
    try:
        cursor = conn.cursor()
        current_metrics = fetch_current_digests(cursor)
        cursor.close()

        # Compute interval delta
        deltas = calculator.calculate_deltas(current_metrics)

        # Persist deltas to qpa_metrics
        snapshot_id, recorded_count = persist_snapshot(conn, current_metrics, deltas)
        print(f"[{time.strftime('%X')}] Snapshot #{snapshot_id}: Recorded {recorded_count} active queries in interval.")
    except Exception as e:
        print(f"Error during metrics collection: {e}")
    finally:
        conn.close()

def start_collector():
    print(f"Starting QPA Historical Collector for schema '{TARGET_SCHEMA}'...")
    print(f"Polling interval: {POLL_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")

    # Run one immediate baseline collection on startup
    collect_metrics_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(collect_metrics_job, 'interval', seconds=POLL_INTERVAL_SECONDS)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Collector stopped.")

if __name__ == "__main__":
    start_collector()