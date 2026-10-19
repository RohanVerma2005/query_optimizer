import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
from typing import Optional, Tuple
from config.database import get_connection
from explainer.query_sampler import reconstruct_executable_query
from explainer.plan_parser import PlanParser, ParsedPlan

parser = PlanParser()


def run_explain_for_digest(digest_text: str) -> Tuple[Optional[ParsedPlan], Optional[str]]:
    """
    Reconstructs an executable SQL statement, runs EXPLAIN FORMAT=JSON,
    and returns (ParsedPlan, executable_sql_used).
    """
    executable_sql = reconstruct_executable_query(digest_text)
    if not executable_sql:
        return None, None

    conn = get_connection(include_db=True)
    cursor = conn.cursor()

    try:
        explain_sql = f"EXPLAIN FORMAT=JSON {executable_sql}"
        cursor.execute(explain_sql)
        row = cursor.fetchone()

        if not row or not row[0]:
            return None, executable_sql

        raw_plan = json.loads(row[0])
        parsed_plan = parser.parse(raw_plan)
        return parsed_plan, executable_sql

    except Exception as e:
        # Some digests (e.g. DDL or invalid syntax) cannot be explained
        return None, f"Execution failed: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def diagnose_top_offenders(limit=5):
    """
    Fetches the top resource-intensive queries from qpa_metrics
    and generates an automated EXPLAIN diagnosis for each.
    """
    conn = get_connection(include_db=False)
    cursor = conn.cursor(dictionary=True)

    query = """
            SELECT c.digest_hash, \
                   c.digest_text, \
                   SUM(i.delta_exec_count)                                                   AS total_execs, \
                   ROUND(SUM(i.delta_total_ms), 2)                                           AS total_time_ms, \
                   ROUND(SUM(i.delta_rows_examined) / NULLIF(SUM(i.delta_exec_count), 0), 0) AS avg_examined
            FROM qpa_metrics.query_interval_stats i
                     JOIN qpa_metrics.query_catalog c ON i.digest_hash = c.digest_hash
            GROUP BY c.digest_hash, c.digest_text
            ORDER BY total_time_ms DESC
                LIMIT %s; \
            """
    cursor.execute(query, (limit,))
    offenders = cursor.fetchall()
    cursor.close()
    conn.close()

    diagnoses = []
    for item in offenders:
        plan, sql_used = run_explain_for_digest(item['digest_text'])
        diagnoses.append({
            "digest_hash": item['digest_hash'],
            "digest_text": item['digest_text'],
            "total_time_ms": item['total_time_ms'],
            "avg_examined": item['avg_examined'],
            "executable_sql": sql_used,
            "parsed_plan": plan
        })
    return diagnoses


if __name__ == "__main__":
    from tabulate import tabulate

    print("\nRunning automated EXPLAIN diagnostics on top offenders...\n")
    results = diagnose_top_offenders(limit=4)

    for idx, res in enumerate(results, start=1):
        print(f"[{idx}] DIGEST: {res['digest_text'][:80]}...")
        print(f"    Total Time: {res['total_time_ms']} ms | Avg Rows Examined: {res['avg_examined']}")

        plan: ParsedPlan = res['parsed_plan']
        if not plan:
            print(f"    Could not generate execution plan: {res['executable_sql']}\n")
            continue

        print(f"    Optimizer Query Cost: {plan.total_cost}")
        findings_data = [
            {
                "Severity": f.severity,
                "Table": f.table_name,
                "Issue": f.issue_type,
                "Diagnosis": f.description
            }
            for f in plan.findings
        ]

        if findings_data:
            print(tabulate(findings_data, headers="keys", tablefmt="simple_grid"))
        else:
            print("    ✓ Query plan is clean (indexed lookups, no filesort or full scans).")
        print("\n" + "-" * 80 + "\n")