import pytest
from collector.delta_calculator import DeltaCalculator, RawDigestMetric

def test_initial_snapshot_skipped():
    calc = DeltaCalculator()
    raw = {
        "hash1": RawDigestMetric("hash1", "db", "SELECT 1", count_star=10, sum_timer_wait_ms=100.0, sum_rows_examined=1000, sum_rows_sent=10)
    }
    deltas = calc.calculate_deltas(raw)
    assert len(deltas) == 0  # Baseline registered; no delta recorded yet

def test_normal_delta_calculation():
    calc = DeltaCalculator()
    raw1 = {"hash1": RawDigestMetric("hash1", "db", "SELECT 1", 10, 100.0, 1000, 10)}
    raw2 = {"hash1": RawDigestMetric("hash1", "db", "SELECT 1", 15, 160.0, 1500, 15)}

    calc.calculate_deltas(raw1)
    deltas = calc.calculate_deltas(raw2)

    assert len(deltas) == 1
    d = deltas[0]
    assert d.delta_exec_count == 5
    assert d.delta_total_ms == 60.0
    assert d.avg_latency_ms == 12.0
    assert d.delta_rows_examined == 500
    assert d.delta_rows_sent == 5
    assert d.examined_to_sent_ratio == 100.0

def test_mysql_counter_reset_recovery():
    calc = DeltaCalculator()
    # Baseline
    raw1 = {"hash1": RawDigestMetric("hash1", "db", "SELECT 1", 100, 1000.0, 10000, 100)}
    calc.calculate_deltas(raw1)

    # Server restarted: counters dropped to lower values
    raw_restart = {"hash1": RawDigestMetric("hash1", "db", "SELECT 1", 5, 50.0, 500, 5)}
    deltas = calc.calculate_deltas(raw_restart)

    assert len(deltas) == 1
    d = deltas[0]
    # Current value must be treated as the fresh baseline, never negative
    assert d.delta_exec_count == 5
    assert d.delta_total_ms == 50.0
    assert d.delta_rows_examined == 500