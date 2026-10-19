import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.database import get_connection

def get_top_offenders(limit=5, sort_by="total_time"):
    """
    Ranks queries from qpa_metrics.
    sort_by options: 'total_time', 'avg_latency', 'efficiency'
    """
    order_clause = {
        "total_time": "total_time_ms DESC",
        "avg_latency": "avg_latency_ms DESC",
        "efficiency": "avg_efficiency_ratio DESC"
    }.get(sort_by, "total_time_ms DESC")

    query = f"""
    SELECT 
        c.digest_hash,
        SUBSTRING(c.digest_text, 1, 75) AS query_preview,
        SUM(i.delta_exec_count) AS total_executions,
        ROUND(SUM(i.delta_total_ms), 2) AS total_time_ms,
        ROUND(SUM(i.delta_total_ms) / NULLIF(SUM(i.delta_exec_count), 0), 2) AS avg_latency_ms,
        ROUND(SUM(i.delta_rows_examined) / NULLIF(SUM(i.delta_exec_count), 0), 0) AS avg_rows_examined,
        ROUND(SUM(i.delta_rows_examined) / NULLIF(SUM(i.delta_rows_sent), 0), 1) AS avg_efficiency_ratio
    FROM qpa_metrics.query_interval_stats i
    JOIN qpa_metrics.query_catalog c ON i.digest_hash = c.digest_hash
    GROUP BY c.digest_hash, c.digest_text
    HAVING total_executions > 0
    ORDER BY {order_clause}
    LIMIT %s;
    """

    conn = get_connection(include_db=False)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, (limit,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    from tabulate import tabulate
    results = get_top_offenders(limit=5, sort_by="total_time")
    print(tabulate(results, headers="keys", tablefmt="fancy_grid"))