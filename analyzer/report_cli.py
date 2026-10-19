import sys
from pathlib import Path

# Ensure project root is first in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tabulate import tabulate
from analyzer.top_offenders import get_top_offenders
from analyzer.regression_detector import detect_regressions
from explainer.explain_runner import diagnose_top_offenders
from optimizer.index_advisor import IndexAdvisor
from optimizer.index_validator import IndexValidator
from optimizer.index_catalog import IndexCatalog
from rewriter.rewrite_engine import QueryRewriteEngine


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def run_cli_report():
    print_banner("Query Performance Analyzer - Diagnostic Report")

    # 1. Top Offenders by Total Consumption
    print("\n[!] Top 5 Resource-Intensive Queries (Total Execution Time):")
    top_time = get_top_offenders(limit=5, sort_by="total_time")
    if top_time:
        print(tabulate(top_time, headers="keys", tablefmt="rounded_grid"))
    else:
        print("No historical metrics captured yet.")

    # 2. Performance Regressions
    print("\n[!] Active Performance Regressions (> 20% Latency Spike):")
    regressions = detect_regressions(recent_snapshots_count=3, threshold_pct=20.0)
    if regressions:
        table_data = [r.__dict__ for r in regressions]
        print(tabulate(table_data, headers="keys", tablefmt="heavy_grid"))
    else:
        print("  ✓ No performance regressions detected across active windows.")

    # 3. Automated EXPLAIN Plan Diagnostics
    print_banner("Automated EXPLAIN Plan Diagnostics")
    diagnoses = diagnose_top_offenders(limit=3)
    for idx, d in enumerate(diagnoses, start=1):
        print(f"\nQuery #{idx}: {d['digest_text'][:85]}...")
        plan = d['parsed_plan']
        if plan and plan.findings:
            table_findings = [
                {
                    "Severity": f.severity,
                    "Target Table": f.table_name,
                    "Issue Type": f.issue_type,
                    "Diagnosis": f.description
                }
                for f in plan.findings
            ]
            print(tabulate(table_findings, headers="keys", tablefmt="fancy_grid"))

    # 4. Validated Index Recommendations
    print_banner("Validated Index Recommendations (ESR Heuristic)")
    advisor = IndexAdvisor()
    validator = IndexValidator()

    validated_recs = []
    for d in diagnoses:
        recs = advisor.recommend_indexes_for_query(d['digest_text'])
        for rec in recs:
            v_res = validator.validate_recommendation(d['digest_text'], rec)
            if v_res and v_res.is_beneficial:
                validated_recs.append({
                    "Target Table": rec.table_name,
                    "Columns": ", ".join(rec.columns),
                    "Baseline Cost": v_res.baseline_cost,
                    "Optimized Cost": v_res.optimized_cost,
                    "Cost Reduction": f"{v_res.cost_reduction_pct}%",
                    "Recommended DDL": rec.create_statement
                })

    if validated_recs:
        print(tabulate(validated_recs, headers="keys", tablefmt="grid"))
    else:
        print("  ✓ No missing indexes detected or queries already well-covered.")

    # 5. Query Rewrite Suggestions
    print_banner("Automated Query Rewrite Suggestions")
    rewrite_engine = QueryRewriteEngine()
    total_rewrites = 0

    for idx, d in enumerate(diagnoses, start=1):
        suggestions = rewrite_engine.analyze_and_rewrite(d['digest_text'])
        if suggestions:
            total_rewrites += len(suggestions)
            print(f"\nTarget Query #{idx}: {d['digest_text'][:80]}...")
            table_data = [
                {
                    "Rule": f"[{s.rule_id}] {s.rule_name}",
                    "Severity": s.severity,
                    "Suggested Rewrite": s.rewritten_sql,
                    "Reason & Benefit": f"{s.explanation} -> {s.expected_benefit}"
                }
                for s in suggestions
            ]
            print(tabulate(table_data, headers="keys", tablefmt="rounded_grid"))

    if total_rewrites == 0:
        print("  ✓ No anti-pattern rewrites needed for top queries.")

    # 6. Unused Dead-Weight Indexes
    print_banner("Unused Indexes Check (sys.schema_unused_indexes)")
    catalog = IndexCatalog()
    unused = catalog.get_unused_indexes()
    if unused:
        print(tabulate(unused, headers="keys", tablefmt="rounded_grid"))
    else:
        print("  ✓ No unused secondary indexes detected.")

    print("\n")


if __name__ == "__main__":
    run_cli_report()