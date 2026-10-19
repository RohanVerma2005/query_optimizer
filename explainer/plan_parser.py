import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class PlanFinding:
    severity: str  # CRITICAL, WARNING, INFO
    table_name: str
    issue_type: str  # FULL_TABLE_SCAN, FILESORT, TEMP_TABLE, HIGH_ROWS_EXAMINED
    description: str
    rows_examined: int
    query_cost: float


@dataclass
class ParsedPlan:
    total_cost: float
    findings: List[PlanFinding] = field(default_factory=list)
    has_full_scan: bool = False
    has_filesort: bool = False
    has_temporary_table: bool = False


class PlanParser:
    def parse(self, plan_json: Dict[str, Any]) -> ParsedPlan:
        query_block = plan_json.get("query_block", {})
        total_cost = float(query_block.get("cost_info", {}).get("query_cost", "0.0") or 0.0)

        parsed = ParsedPlan(total_cost=round(total_cost, 2))
        self._traverse_node(query_block, parsed)
        return parsed

    def _traverse_node(self, node: Dict[str, Any], result: ParsedPlan):
        if not isinstance(node, dict):
            return

        # 1. Check for temporary table usage at the block level
        if node.get("using_temporary_table") is True:
            result.has_temporary_table = True
            result.findings.append(PlanFinding(
                severity="WARNING",
                table_name="<intermediate_tmp_table>",
                issue_type="TEMP_TABLE",
                description="Query generates an intermediate temporary table during execution.",
                rows_examined=0,
                query_cost=result.total_cost
            ))

        # 2. Check for filesort at block or ordering level
        if node.get("using_filesort") is True or "ordering_operation" in node:
            result.has_filesort = True
            sort_table = node.get("table", {}).get("table_name", "<query_block>")
            result.findings.append(PlanFinding(
                severity="WARNING",
                table_name=sort_table,
                issue_type="FILESORT",
                description="MySQL must perform a filesort operation to produce sorted order.",
                rows_examined=0,
                query_cost=result.total_cost
            ))

        # 3. Inspect individual table scan access operations
        if "table" in node:
            tbl_info = node["table"]
            table_name = tbl_info.get("table_name", "unknown")
            access_type = tbl_info.get("access_type", "").upper()
            rows_examined = int(tbl_info.get("rows_examined_per_scan", 0) or 0)
            cost = float(tbl_info.get("cost_info", {}).get("prefix_cost", "0.0") or 0.0)

            # Detect Full Table Scan
            if access_type == "ALL":
                result.has_full_scan = True
                result.findings.append(PlanFinding(
                    severity="CRITICAL" if rows_examined > 1000 else "WARNING",
                    table_name=table_name,
                    issue_type="FULL_TABLE_SCAN",
                    description=f"Full table scan on '{table_name}'. Evaluates all {rows_examined:,} rows without index lookup.",
                    rows_examined=rows_examined,
                    query_cost=round(cost, 2)
                ))
            elif access_type == "INDEX":
                result.findings.append(PlanFinding(
                    severity="WARNING",
                    table_name=table_name,
                    issue_type="FULL_INDEX_SCAN",
                    description=f"Full index scan on '{table_name}'. Traverses entire index tree ({rows_examined:,} rows).",
                    rows_examined=rows_examined,
                    query_cost=round(cost, 2)
                ))

            # Detect low filter percentage (wasteful row evaluation)
            filtered_pct = float(tbl_info.get("filtered", "100.0") or 100.0)
            if filtered_pct < 20.0 and rows_examined > 500:
                result.findings.append(PlanFinding(
                    severity="WARNING",
                    table_name=table_name,
                    issue_type="HIGH_ROWS_EXAMINED",
                    description=f"Only {filtered_pct:.1f}% of examined rows from '{table_name}' satisfy the WHERE predicate.",
                    rows_examined=rows_examined,
                    query_cost=round(cost, 2)
                ))

        # 4. Recursively traverse nested joins, ordering, groupings, subqueries
        for key, value in node.items():
            if isinstance(value, dict):
                self._traverse_node(value, result)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._traverse_node(item, result)