import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass, field
from typing import Dict, List, Set
import sqlglot
from sqlglot import exp

@dataclass
class TablePredicates:
    table_name: str
    equality_cols: Set[str] = field(default_factory=set)
    range_cols: Set[str] = field(default_factory=set)
    join_cols: Set[str] = field(default_factory=set)
    order_cols: List[str] = field(default_factory=list)

class QueryASTParser:
    def __init__(self, default_schema="qpa_workload"):
        self.default_schema = default_schema

    def extract_predicates(self, sql: str) -> Dict[str, TablePredicates]:
        """
        Parses SQL and extracts table-level predicate usage.
        Returns a dictionary mapping: table_name -> TablePredicates
        """
        predicates_by_table: Dict[str, TablePredicates] = {}

        try:
            # Clean backticks and parse using MySQL dialect
            cleaned_sql = sql.replace("`", "")
            parsed = sqlglot.parse_one(cleaned_sql, read="mysql")
        except Exception:
            return predicates_by_table

        # 1. Map table aliases to actual table names
        alias_map = {}
        for tbl in parsed.find_all(exp.Table):
            t_name = tbl.name.lower()
            alias = tbl.alias.lower() if tbl.alias else t_name
            alias_map[alias] = t_name
            if t_name not in predicates_by_table:
                predicates_by_table[t_name] = TablePredicates(table_name=t_name)

        # Helper to normalize column and resolve table name
        def resolve_col(column_expr: exp.Column):
            col_name = column_expr.name.lower()
            tbl_ref = column_expr.table.lower() if column_expr.table else None
            tbl_name = alias_map.get(tbl_ref) if tbl_ref else None

            # Fallback if single table query
            if not tbl_name and len(alias_map) == 1:
                tbl_name = list(alias_map.values())[0]

            return tbl_name, col_name

        # 2. Extract JOIN ON columns
        for join in parsed.find_all(exp.Join):
            on_clause = join.args.get("on")
            if on_clause:
                for eq in on_clause.find_all(exp.EQ):
                    left, right = eq.left, eq.right
                    if isinstance(left, exp.Column) and isinstance(right, exp.Column):
                        t1, c1 = resolve_col(left)
                        t2, c2 = resolve_col(right)
                        if t1 and t1 in predicates_by_table:
                            predicates_by_table[t1].join_cols.add(c1)
                        if t2 and t2 in predicates_by_table:
                            predicates_by_table[t2].join_cols.add(c2)

        # 3. Extract WHERE clause columns
        where_clause = parsed.find(exp.Where)
        if where_clause:
            # Equality comparisons
            for eq in where_clause.find_all(exp.EQ):
                # Avoid counting JOIN conditions if placed in WHERE
                if isinstance(eq.left, exp.Column) and not isinstance(eq.right, exp.Column):
                    t, c = resolve_col(eq.left)
                    if t and t in predicates_by_table:
                        predicates_by_table[t].equality_cols.add(c)
                elif isinstance(eq.right, exp.Column) and not isinstance(eq.left, exp.Column):
                    t, c = resolve_col(eq.right)
                    if t and t in predicates_by_table:
                        predicates_by_table[t].equality_cols.add(c)

            # Range comparisons (<, <=, >, >=, BETWEEN, LIKE)
            for r_node in where_clause.find_all((exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between, exp.Like)):
                for col in r_node.find_all(exp.Column):
                    t, c = resolve_col(col)
                    if t and t in predicates_by_table and c not in predicates_by_table[t].equality_cols:
                        predicates_by_table[t].range_cols.add(c)

        # 4. Extract ORDER BY columns
        order_clause = parsed.find(exp.Order)
        if order_clause:
            for ordered in order_clause.find_all(exp.Ordered):
                col = ordered.find(exp.Column)
                if col:
                    t, c = resolve_col(col)
                    if t and t in predicates_by_table:
                        if c not in predicates_by_table[t].order_cols:
                            predicates_by_table[t].order_cols.append(c)

        return predicates_by_table

if __name__ == "__main__":
    sample_sql = """
    SELECT c.full_name, o.total_amount
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    WHERE o.order_status = 'COMPLETED' AND o.created_at >= '2025-01-01'
    ORDER BY o.total_amount DESC;
    """
    parser = QueryASTParser()
    res = parser.extract_predicates(sample_sql)
    for tbl, p in res.items():
        print(f"Table: {tbl}")
        print(f"  Equality: {p.equality_cols}")
        print(f"  Range:    {p.range_cols}")
        print(f"  Join:     {p.join_cols}")
        print(f"  Order By: {p.order_cols}")