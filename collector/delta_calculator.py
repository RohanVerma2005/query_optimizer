import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

@dataclass
class RawDigestMetric:
    digest_hash: str
    schema_name: str
    digest_text: str
    count_star: int
    sum_timer_wait_ms: float
    sum_rows_examined: int
    sum_rows_sent: int

@dataclass
class DeltaMetric:
    digest_hash: str
    delta_exec_count: int
    delta_total_ms: float
    avg_latency_ms: float
    delta_rows_examined: int
    delta_rows_sent: int
    examined_to_sent_ratio: float

class DeltaCalculator:
    def __init__(self):
        # Maps digest_hash -> previous RawDigestMetric
        self._previous_state: Dict[str, RawDigestMetric] = {}

    def calculate_deltas(self, current_metrics: Dict[str, RawDigestMetric]) -> list[DeltaMetric]:
        deltas: list[DeltaMetric] = []

        for digest_hash, curr in current_metrics.items():
            if digest_hash not in self._previous_state:
                # First time seeing this query in memory: save baseline and skip recording 0-delta
                self._previous_state[digest_hash] = curr
                continue

            prev = self._previous_state[digest_hash]

            # Detect server restart or counter reset (current is strictly less than previous)
            is_reset = (
                curr.count_star < prev.count_star or
                curr.sum_timer_wait_ms < prev.sum_timer_wait_ms or
                curr.sum_rows_examined < prev.sum_rows_examined
            )

            if is_reset:
                # Counter was reset: treat current value as fresh delta baseline
                d_exec = curr.count_star
                d_time = curr.sum_timer_wait_ms
                d_examined = curr.sum_rows_examined
                d_sent = curr.sum_rows_sent
            else:
                d_exec = curr.count_star - prev.count_star
                d_time = curr.sum_timer_wait_ms - prev.sum_timer_wait_ms
                d_examined = curr.sum_rows_examined - prev.sum_rows_examined
                d_sent = curr.sum_rows_sent - prev.sum_rows_sent

            # Update cache to current values
            self._previous_state[digest_hash] = curr

            # Only record if the query actually executed during this interval
            if d_exec > 0:
                avg_latency = round(d_time / d_exec, 3)
                # Compute rows ratio with division-by-zero protection
                ratio = round(d_examined / max(d_sent, 1), 2)

                deltas.append(DeltaMetric(
                    digest_hash=digest_hash,
                    delta_exec_count=d_exec,
                    delta_total_ms=round(d_time, 2),
                    avg_latency_ms=avg_latency,
                    delta_rows_examined=d_examined,
                    delta_rows_sent=d_sent,
                    examined_to_sent_ratio=ratio
                ))

        return deltas