import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
import pandas as pd
import plotly.express as px
from config.database import get_connection
from analyzer.top_offenders import get_top_offenders
from analyzer.regression_detector import detect_regressions
from explainer.explain_runner import diagnose_top_offenders
from optimizer.index_advisor import IndexAdvisor
from optimizer.index_validator import IndexValidator
from rewriter.rewrite_engine import QueryRewriteEngine

st.set_page_config(page_title="Query Performance Analyzer", page_icon="", layout="wide")

st.title("Query Performance Analyzer & Optimizer")
st.markdown("Continuous SQL Telemetry, Automated Diagnostics & Index Recommendations")

# Sidebar
st.sidebar.header("Controls & Settings")
poll_rate = st.sidebar.slider("Auto-Refresh Rate (seconds)", 5, 60, 15)
if st.sidebar.button("Refresh Telemetry"):
    st.rerun()

# --- Section 1: KPI Metrics ---
conn = get_connection(include_db=False)
cursor = conn.cursor(dictionary=True)

try:
    cursor.execute("SELECT COUNT(*) AS total_snapshots FROM qpa_metrics.metric_snapshots;")
    snap_count = cursor.fetchone()['total_snapshots']

    cursor.execute("SELECT COUNT(*) AS total_queries FROM qpa_metrics.query_catalog;")
    query_count = cursor.fetchone()['total_queries']

    cursor.execute("SELECT ROUND(SUM(delta_total_ms), 1) AS total_cpu_time FROM qpa_metrics.query_interval_stats;")
    cpu_ms = cursor.fetchone()['total_cpu_time'] or 0.0
finally:
    cursor.close()
    conn.close()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Captured Snapshots", snap_count)
col2.metric("Tracked Query Patterns", query_count)
col3.metric("Total Engine Time", f"{cpu_ms/1000:.2f} s")
regressions = detect_regressions(recent_snapshots_count=3, threshold_pct=20.0)
col4.metric("Active Regressions", len(regressions), delta=f"{len(regressions)} Spikes", delta_color="inverse")

st.divider()

if regressions:
    st.error("Active Query Latency Regressions Detected!")
    reg_df = pd.DataFrame([r.__dict__ for r in regressions])
    st.dataframe(reg_df[['status', 'query_preview', 'baseline_avg_ms', 'recent_avg_ms', 'percentage_change']], use_container_width=True)

st.subheader("Query Latency Over Time (Per Snapshot)")
conn = get_connection(include_db=False)
try:
    timeline_query = """
    SELECT 
        s.captured_at,
        SUBSTRING(c.digest_text, 1, 45) AS query_name,
        i.avg_latency_ms
    FROM qpa_metrics.query_interval_stats i
    JOIN qpa_metrics.metric_snapshots s ON i.snapshot_id = s.id
    JOIN qpa_metrics.query_catalog c ON i.digest_hash = c.digest_hash
    ORDER BY s.id DESC
    LIMIT 150;
    """
    df_timeline = pd.read_sql(timeline_query, conn)
    if not df_timeline.empty:
        fig = px.line(
            df_timeline,
            x="captured_at",
            y="avg_latency_ms",
            color="query_name",
            title="Query Latency Trends",
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Awaiting more interval snapshots to display trends.")
finally:
    conn.close()

tab1, tab2, tab3 = st.tabs(["Top Resource Hogs", "Index Recommendations", "Rewrite Suggestions"])

with tab1:
    offenders = get_top_offenders(limit=10, sort_by="total_time")
    if offenders:
        df_offenders = pd.DataFrame(offenders)
        st.dataframe(df_offenders[['query_preview', 'total_executions', 'total_time_ms', 'avg_latency_ms', 'avg_rows_examined', 'avg_efficiency_ratio']], use_container_width=True)
    else:
        st.write("No metrics logged yet.")

with tab2:
    st.markdown("#### Validated Index Proposals (ESR Heuristic)")
    advisor = IndexAdvisor()
    validator = IndexValidator()
    top_diagnoses = diagnose_top_offenders(limit=5)

    has_index = False
    for d in top_diagnoses:
        recs = advisor.recommend_indexes_for_query(d['digest_text'])
        for rec in recs:
            v_res = validator.validate_recommendation(d['digest_text'], rec)
            if v_res and v_res.is_beneficial:
                has_index = True
                with st.expander(f"{rec.table_name.upper()} — Suggestion (+{v_res.cost_reduction_pct}% cost reduction)"):
                    st.write(f"**Target Columns:** `{', '.join(rec.columns)}`")
                    st.write(f"**Reason:** {rec.reason}")
                    st.code(rec.create_statement, language="sql")
                    c1, c2 = st.columns(2)
                    c1.metric("Baseline Optimizer Cost", v_res.baseline_cost)
                    c2.metric("Optimized Cost", v_res.optimized_cost, delta=f"-{v_res.cost_reduction_pct}%")

    if not has_index:
        st.success("No missing indexes detected for current top queries.")

with tab3:
    st.markdown("#### AST Query Rewrites")
    engine = QueryRewriteEngine()
    has_rewrites = False
    for d in top_diagnoses:
        suggs = engine.analyze_and_rewrite(d['digest_text'])
        for s in suggs:
            has_rewrites = True
            with st.expander(f"[{s.rule_id}] {s.rule_name} ({s.severity})"):
                st.write(f"**Explanation:** {s.explanation}")
                st.write(f"**Expected Benefit:** {s.expected_benefit}")
                st.code(s.rewritten_sql, language="sql")

    if not has_rewrites:
        st.success("No anti-patterns requiring rewrites detected.")
