import pytest
from optimizer.ast_parser import QueryASTParser

def test_extract_where_and_order_predicates():
    parser = QueryASTParser()
    sql = "SELECT id, full_name FROM customers WHERE country = 'USA' AND created_at >= '2025-01-01' ORDER BY full_name"
    predicates = parser.extract_predicates(sql)

    assert "customers" in predicates
    cust = predicates["customers"]
    assert "country" in cust.equality_cols
    assert "created_at" in cust.range_cols
    assert "full_name" in cust.order_cols

def test_extract_multi_table_join_predicates():
    parser = QueryASTParser()
    sql = """
    SELECT c.id, o.id 
    FROM customers c 
    JOIN orders o ON c.id = o.customer_id 
    WHERE o.order_status = 'PENDING'
    """
    predicates = parser.extract_predicates(sql)

    assert "customers" in predicates
    assert "orders" in predicates
    assert "id" in predicates["customers"].join_cols
    assert "customer_id" in predicates["orders"].join_cols
    assert "order_status" in predicates["orders"].equality_cols