import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from typing import List
import sqlglot
from explainer.query_sampler import reconstruct_executable_query
from rewriter.rules_base import RewriteSuggestion
from rewriter.rules_library import (
    SelectStarRule,
    NonSargableFunctionRule,
    LeadingWildcardLikeRule,
    DeepOffsetPaginationRule
)

class QueryRewriteEngine:
    def __init__(self):
        self.rules = [
            NonSargableFunctionRule(),
            LeadingWildcardLikeRule(),
            DeepOffsetPaginationRule(),
            SelectStarRule()
        ]

    def analyze_and_rewrite(self, sql_digest: str) -> List[RewriteSuggestion]:
        executable_sql = reconstruct_executable_query(sql_digest)
        if not executable_sql:
            return []

        suggestions: List[RewriteSuggestion] = []
        try:
            cleaned_sql = executable_sql.replace("`", "")
            parsed = sqlglot.parse_one(cleaned_sql, read="mysql")
        except Exception:
            return []

        for rule in self.rules:
            res = rule.evaluate(parsed, executable_sql)
            if res:
                suggestions.append(res)

        return suggestions

if __name__ == "__main__":
    engine = QueryRewriteEngine()
    test_queries = [
        "SELECT * FROM orders WHERE YEAR(created_at) = 2025",
        "SELECT * FROM products WHERE description LIKE '%test%'",
        "SELECT * FROM customers ORDER BY id LIMIT 50 OFFSET 5000"
    ]

    for q in test_queries:
        print(f"\nEvaluating: {q}")
        findings = engine.analyze_and_rewrite(q)
        for f in findings:
            print(f"  [{f.rule_id}] {f.rule_name} ({f.severity})")
            print(f"  Explanation: {f.explanation}")
            print(f"  Suggested:   {f.rewritten_sql}")