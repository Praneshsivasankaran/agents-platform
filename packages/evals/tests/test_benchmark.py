"""Tests for the offline latency benchmark harness (packages/evals/benchmark.py)."""

from __future__ import annotations

import pytest

from evals.benchmark import BenchmarkResult, benchmark, percentile, _reference_workload, main


# ---------------------------------------------------------------------------
# percentile()
# ---------------------------------------------------------------------------

def test_percentile_basic_ordering():
    samples = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(samples, 0) == 10.0
    assert percentile(samples, 100) == 50.0
    assert percentile(samples, 50) == 30.0
    # Monotonic non-decreasing across rising percentiles.
    vals = [percentile(samples, p) for p in (0, 25, 50, 75, 90, 95, 99, 100)]
    assert vals == sorted(vals)


def test_percentile_interpolates():
    # type-7: p50 of [0, 100] = 50.0 (interpolated between the two points)
    assert percentile([0.0, 100.0], 50) == pytest.approx(50.0)


def test_percentile_single_sample():
    assert percentile([7.5], 95) == 7.5


def test_percentile_rejects_empty():
    with pytest.raises(ValueError, match="at least one sample"):
        percentile([], 50)


def test_percentile_rejects_out_of_range():
    with pytest.raises(ValueError):
        percentile([1.0], 150)


# ---------------------------------------------------------------------------
# benchmark()
# ---------------------------------------------------------------------------

def test_benchmark_returns_valid_report():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1

    result = benchmark(fn, iterations=20, warmup=5, label="unit.noop")
    assert isinstance(result, BenchmarkResult)
    assert result.iterations == 20
    assert result.warmup == 5
    # warmup + iterations calls happened.
    assert calls["n"] == 25
    # Percentile ordering invariant.
    assert result.min_ms <= result.p50_ms <= result.p90_ms <= result.p95_ms <= result.p99_ms <= result.max_ms
    assert result.min_ms <= result.mean_ms <= result.max_ms
    assert result.total_s >= 0.0


def test_benchmark_zero_warmup_runs_only_iterations():
    calls = {"n": 0}
    benchmark(lambda: calls.__setitem__("n", calls["n"] + 1), iterations=10, warmup=0)
    assert calls["n"] == 10


def test_benchmark_rejects_zero_iterations():
    with pytest.raises(ValueError, match="iterations must be >= 1"):
        benchmark(lambda: None, iterations=0)


def test_benchmark_rejects_negative_warmup():
    with pytest.raises(ValueError, match="warmup must be >= 0"):
        benchmark(lambda: None, iterations=1, warmup=-1)


def test_benchmark_propagates_callable_exception():
    def boom():
        raise RuntimeError("workload failed")

    with pytest.raises(RuntimeError, match="workload failed"):
        benchmark(boom, iterations=3)


def test_result_is_immutable():
    result = benchmark(lambda: None, iterations=2)
    with pytest.raises(Exception):
        result.p50_ms = 999.0  # CoreContractModel is frozen


def test_result_format_and_json_roundtrip():
    result = benchmark(lambda: None, iterations=3, label="fmt.test")
    text = result.format()
    assert "fmt.test" in text and "p95=" in text
    restored = BenchmarkResult.model_validate_json(result.model_dump_json())
    assert restored == result


# ---------------------------------------------------------------------------
# module main() — self-demo, offline
# ---------------------------------------------------------------------------

def test_reference_workload_runs():
    _reference_workload()  # must not raise


def test_main_runs_offline(capsys):
    rc = main(["--iterations", "5", "--warmup", "1", "--label", "demo"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "demo" in out
