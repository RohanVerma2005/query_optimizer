import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
from dataclasses import dataclass
from typing import Optional
from config.database import get_connection
from explainer.query_sampler import reconstruct_executable_query
from optimizer.index_advisor import IndexRecommendation

@dataclass
class ValidationResult:
    recommendation: IndexRecommendation
    baseline_cost: float
    optimized_cost: float
    cost_reduction_pct: float
    is_beneficial: bool

class IndexValidator:
    def __init__(self, schema_name="qpa_workload"):
        self.schema_name = schema_name

    def validate_recommendation(self, query_digest: str, rec: IndexRecommendation) -> Optional[ValidationResult]:
        sql = reconstruct_executable_query(query_digest)
        if not sql:
            return None

        conn = get_connection(include_db=True)
        cursor = conn.cursor()

        try:
            # 1. Baseline Cost
            cursor.execute(f"EXPLAIN FORMAT=JSON {sql}")
            raw_base = json.loads(cursor.fetchone()[0])
            base_cost = float(raw_base.get("query_block", {}).get("cost_info", {}).get("query_cost", "0.0") or 0.0)

            # 2. Create index as INVISIBLE for isolated testing
            cols_str = ", ".join(f"`{c}`" for c in rec.columns)
            temp_idx_name = f"qpa_test_{rec.index_name}"[:60]
            create_sql = f"CREATE INDEX `{temp_idx_name}` ON `{rec.table_name}` ({cols_str}) INVISIBLE"
            cursor.execute(create_sql)

            # 3. Evaluate cost with invisible indexes turned ON for this session
            cursor.execute("SET SESSION optimizer_switch = 'use_invisible_indexes=on'")
            cursor.execute(f"EXPLAIN FORMAT=JSON {sql}")
            raw_opt = json.loads(cursor.fetchone()[0])
            opt_cost = float(raw_opt.get("query_block", {}).get("cost_info", {}).get("query_cost", "0.0") or 0.0)

            # Reset session switch
            cursor.execute("SET SESSION optimizer_switch = 'use_invisible_indexes=off'")

            # 4. Drop the test index immediately
            cursor.execute(f"DROP INDEX `{temp_idx_name}` ON `{rec.table_name}`")

            # 5. Calculate cost improvement
            cost_reduction = 0.0
            if base_cost > 0:
                cost_reduction = round(((base_cost - opt_cost) / base_cost) * 100.0, 1)

            return ValidationResult(
                recommendation=rec,
                baseline_cost=round(base_cost, 2),
                optimized_cost=round(opt_cost, 2),
                cost_reduction_pct=cost_reduction,
                is_beneficial=cost_reduction >= 20.0 or (base_cost > opt_cost and opt_cost < 50.0)
            )

        except Exception as e:
            # Clean up index if error happened mid-execution
            try:
                cursor.execute(f"DROP INDEX `{temp_idx_name}` ON `{rec.table_name}`")
            except Exception:
                pass
            return None
        finally:
            cursor.close()
            conn.close()