import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import re
import sqlglot
from sqlglot import exp
from typing import Optional
from rewriter.rules_base import BaseRewriteRule, RewriteSuggestion


class SelectStarRule(BaseRewriteRule):
    rule_id = "RW001"
    rule_name = "Avoid SELECT *"
    severity = "MEDIUM"

    def evaluate(self, parsed: sqlglot.exp.Expression, raw_sql: str) -> Optional[RewriteSuggestion]:
        # Check if query projects wildcard star
        stars = list(parsed.find_all(exp.Star))
        if not stars:
            return None

        return RewriteSuggestion(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            original_sql=raw_sql.strip(),
            rewritten_sql="SELECT <explicit_columns> FROM ...",
            explanation="SELECT * fetches unused columns (e.g. TEXT, BLOB payloads), inflates network I/O, and prevents covering index optimizations.",
            expected_benefit="Enables index-only scans (covering index) and reduces memory allocation."
        )


class NonSargableFunctionRule(BaseRewriteRule):
    rule_id = "RW002"
    rule_name = "Non-SARGable Function on Column"
    severity = "HIGH"

    def evaluate(self, parsed: sqlglot.exp.Expression, raw_sql: str) -> Optional[RewriteSuggestion]:
        # Direct regex pattern match on the raw query text: YEAR(column_name) = YYYY
        pattern = re.compile(
            r"YEAR\s*\(\s*`?([a-zA-Z0-9_]+)`?\s*\)\s*=\s*['\"]?(\d{4})['\"]?",
            re.IGNORECASE
        )
        match = pattern.search(raw_sql)
        if match:
            col_name = match.group(1)
            target_year = int(match.group(2))
            next_year = target_year + 1

            range_sql = (
                f"{col_name} >= '{target_year}-01-01 00:00:00' AND "
                f"{col_name} < '{next_year}-01-01 00:00:00'"
            )

            rewritten_full = pattern.sub(range_sql, raw_sql)

            return RewriteSuggestion(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                original_sql=raw_sql.strip(),
                rewritten_sql=rewritten_full.strip(),
                explanation=f"Wrapping `{col_name}` in `YEAR()` prevents MySQL from using a B-Tree index on `{col_name}`.",
                expected_benefit="Turns a full table scan into an efficient B-Tree index range scan."
            )

        return None


class LeadingWildcardLikeRule(BaseRewriteRule):
    rule_id = "RW003"
    rule_name = "Leading Wildcard in LIKE Predicate"
    severity = "HIGH"

    def evaluate(self, parsed: sqlglot.exp.Expression, raw_sql: str) -> Optional[RewriteSuggestion]:
        for like in parsed.find_all(exp.Like):
            pattern = like.expression.sql().strip("'").strip('"')
            col = like.this.sql()
            if pattern.startswith("%") or pattern == "?":
                clean_term = pattern.replace("%", "").strip() or "keyword"
                rewritten_text = f"MATCH({col}) AGAINST('{clean_term}' IN NATURAL LANGUAGE MODE)"

                return RewriteSuggestion(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    original_sql=raw_sql.strip(),
                    rewritten_sql=f"SELECT ... WHERE {rewritten_text}",
                    explanation=f"`{col} LIKE '{pattern}'` cannot leverage standard B-Tree index prefixes because of the leading wildcard.",
                    expected_benefit="Replace with a MySQL FULLTEXT index and MATCH() AGAINST() to avoid an O(N) scan."
                )
        return None


class DeepOffsetPaginationRule(BaseRewriteRule):
    rule_id = "RW004"
    rule_name = "Deep OFFSET Pagination"
    severity = "MEDIUM"

    def evaluate(self, parsed: sqlglot.exp.Expression, raw_sql: str) -> Optional[RewriteSuggestion]:
        limit_node = parsed.find(exp.Limit)
        offset_node = parsed.find(exp.Offset)

        has_high_offset = False
        if offset_node:
            offset_val = offset_node.expression.sql()
            if offset_val.isdigit() and int(offset_val) >= 1000:
                has_high_offset = True
            elif offset_val == "?":
                has_high_offset = True

        if not has_high_offset:
            return None

        table_node = parsed.find(exp.Table)
        tbl_name = table_node.name if table_node else "<table>"

        return RewriteSuggestion(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            original_sql=raw_sql.strip(),
            rewritten_sql=f"SELECT t.* FROM {tbl_name} t JOIN (SELECT id FROM {tbl_name} ORDER BY ... LIMIT ... OFFSET ...) AS sub ON t.id = sub.id",
            explanation="High OFFSET requires MySQL to read and discard thousands of full rows before returning results.",
            expected_benefit="Deferred Join pagination scans only index keys for discarded rows, cutting I/O by up to 90%."
        )