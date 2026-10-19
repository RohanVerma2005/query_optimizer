import pytest
from rewriter.rewrite_engine import QueryRewriteEngine

def test_non_sargable_year_rewrite():
    engine = QueryRewriteEngine()
    sql = "SELECT * FROM orders WHERE YEAR(created_at) = 2025"
    suggestions = engine.analyze_and_rewrite(sql)

    rule_ids = [s.rule_id for s in suggestions]
    assert "RW002" in rule_ids  # Non-SARGable rule fired

    sarg_sugg = next(s for s in suggestions if s.rule_id == "RW002")
    assert "created_at >= '2025-01-01 00:00:00'" in sarg_sugg.rewritten_sql
    assert "created_at < '2026-01-01 00:00:00'" in sarg_sugg.rewritten_sql

def test_leading_wildcard_like_rewrite():
    engine = QueryRewriteEngine()
    sql = "SELECT * FROM products WHERE description LIKE '%gadget%'"
    suggestions = engine.analyze_and_rewrite(sql)

    rule_ids = [s.rule_id for s in suggestions]
    assert "RW003" in rule_ids
    wildcard_sugg = next(s for s in suggestions if s.rule_id == "RW003")
    assert "MATCH" in wildcard_sugg.rewritten_sql

def test_select_star_rule():
    engine = QueryRewriteEngine()
    sql = "SELECT * FROM customers WHERE id = 10"
    suggestions = engine.analyze_and_rewrite(sql)

    rule_ids = [s.rule_id for s in suggestions]
    assert "RW001" in rule_ids