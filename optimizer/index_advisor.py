import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass
from typing import List, Optional
from optimizer.ast_parser import QueryASTParser, TablePredicates
from optimizer.index_catalog import IndexCatalog

@dataclass
class IndexRecommendation:
    table_name: str
    columns: List[str]
    index_name: str
    create_statement: str
    reason: str

class IndexAdvisor:
    def __init__(self, schema_name="qpa_workload"):
        self.schema_name = schema_name
        self.parser = QueryASTParser(default_schema=schema_name)
        self.catalog = IndexCatalog(schema_name=schema_name)

    def recommend_indexes_for_query(self, sql: str) -> List[IndexRecommendation]:
        predicates_by_table = self.parser.extract_predicates(sql)
        recommendations: List[IndexRecommendation] = []

        for table_name, preds in predicates_by_table.items():
            # Composite index column ordering rule:
            # 1. Equality filters & Joins
            # 2. ORDER BY sort columns
            # 3. Range filters
            recommended_cols: List[str] = []

            # 1. Equality & Join columns first
            for col in sorted(list(preds.equality_cols | preds.join_cols)):
                if col not in recommended_cols:
                    recommended_cols.append(col)

            # 2. Sort columns second (allows index-driven ordering to avoid filesort)
            for col in preds.order_cols:
                if col not in recommended_cols:
                    recommended_cols.append(col)

            # 3. Range columns last
            for col in sorted(list(preds.range_cols)):
                if col not in recommended_cols:
                    recommended_cols.append(col)

            if not recommended_cols:
                continue

            # Check if this sequence is already satisfied by an existing prefix
            if self.catalog.is_covered_by_existing_index(table_name, recommended_cols):
                continue

            # Generate index name & DDL
            col_suffix = "_".join(recommended_cols)[:30]
            idx_name = f"idx_{table_name}_{col_suffix}"
            cols_clause = ", ".join(f"`{c}`" for c in recommended_cols)
            ddl = f"CREATE INDEX `{idx_name}` ON `{self.schema_name}`.`{table_name}` ({cols_clause});"

            reasons = []
            if preds.equality_cols:
                reasons.append(f"filters on {list(preds.equality_cols)}")
            if preds.join_cols:
                reasons.append(f"joins on {list(preds.join_cols)}")
            if preds.order_cols:
                reasons.append(f"sorts by {preds.order_cols}")
            if preds.range_cols:
                reasons.append(f"range scans on {list(preds.range_cols)}")

            reason_str = "Index candidate for " + "; ".join(reasons)

            recommendations.append(IndexRecommendation(
                table_name=table_name,
                columns=recommended_cols,
                index_name=idx_name,
                create_statement=ddl,
                reason=reason_str
            ))

        return recommendations