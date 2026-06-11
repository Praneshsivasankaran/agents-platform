"""Agent-agnostic latency benchmark harness (offline by default).

Times a caller-supplied zero-argument callable over N iterations and reports wall-clock
percentiles (p50/p90/p95/p99) plus mean/min/max. It runs whatever you hand it — it makes NO
network or provider calls itself, so pointing it at a mock-backed graph is a fully offline
latency profile. (Point it at a live provider only deliberately, never by default.)

Usage (library):
    from evals.benchmark import benchmark
    result = benchmark(lambda: run_graph_once(), iterations=50, warmup=5, label="agent01.text")
    print(result.format())

Usage (module, self-demo over a CPU reference workload):
    PYTHONPATH=packages python -m evals.benchmark --iterations 200 --warmup 20
"""

from __future__ import annotations

import argparse
import math
import time
from typing import Callable

from pydantic import Field

from core.interfaces.base import CoreContractModel


def percentile(samples_ms: list[float], pct: float) -> float:
    """Linear-interpolation percentile (``pct`` in [0, 100]) over a list of millisecond samples.

    Matches the common "type 7" / numpy-default definition. Raises on empty input or an
    out-of-range percentile — a benchmark with no samples is a bug, not a 0.0.
    """
    if not samples_ms:
        raise ValueError("percentile() requires at least one sample")
    if not (0.0 <= pct <= 100.0):
        raise ValueError(f"pct must be in [0, 100], got {pct}")
    ordered = sorted(samples_ms)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    frac = rank - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


class BenchmarkResult(CoreContractModel):
    """Immutable percentile report for one benchmarked callable."""

    label: str = Field(min_length=1)
    iterations: int = Field(ge=1)
    warmup: int = Field(ge=0)
    min_ms: float = Field(ge=0.0)
    p50_ms: float = Field(ge=0.0)
    p90_ms: float = Field(ge=0.0)
    p95_ms: float = Field(ge=0.0)
    p99_ms: float = Field(ge=0.0)
    max_ms: float = Field(ge=0.0)
    mean_ms: float = Field(ge=0.0)
    total_s: float = Field(ge=0.0)

    def format(self) -> str:
        return (
            f"{self.label}: n={self.iterations} (warmup={self.warmup})  "
            f"p50={self.p50_ms:.2f}ms  p90={self.p90_ms:.2f}ms  p95={self.p95_ms:.2f}ms  "
            f"p99={self.p99_ms:.2f}ms  min={self.min_ms:.2f}ms  max={self.max_ms:.2f}ms  "
            f"mean={self.mean_ms:.2f}ms  total={self.total_s:.3f}s"
        )


def benchmark(
    fn: Callable[[], object],
    *,
    iterations: int,
    warmup: int = 0,
    label: str = "benchmark",
) -> BenchmarkResult:
    """Run ``fn`` ``warmup`` times (discarded) then ``iterations`` times (timed).

    Uses ``time.perf_counter`` (monotonic, high-resolution). The callable's return value is
    ignored — only wall-clock per call is measured. Exceptions from ``fn`` propagate (a failing
    workload is not a latency datapoint).
    """
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    if warmup < 0:
        raise ValueError("warmup must be >= 0")

    for _ in range(warmup):
        fn()

    samples_ms: list[float] = []
    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    total_s = time.perf_counter() - t_start

    return BenchmarkResult(
        label=label,
        iterations=iterations,
        warmup=warmup,
        min_ms=min(samples_ms),
        p50_ms=percentile(samples_ms, 50),
        p90_ms=percentile(samples_ms, 90),
        p95_ms=percentile(samples_ms, 95),
        p99_ms=percentile(samples_ms, 99),
        max_ms=max(samples_ms),
        mean_ms=sum(samples_ms) / len(samples_ms),
        total_s=total_s,
    )


def _reference_workload() -> None:
    """A deterministic CPU workload for the module self-demo (no I/O, no network)."""
    total = 0.0
    for i in range(1, 5000):
        total += math.sqrt(i) * math.log(i + 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline latency benchmark harness (self-demo over a CPU reference workload). "
        "Agents call benchmark() with their own offline callable.",
    )
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--label", type=str, default="reference.cpu_workload")
    args = parser.parse_args(argv)

    result = benchmark(
        _reference_workload,
        iterations=args.iterations,
        warmup=args.warmup,
        label=args.label,
    )
    print(result.format())
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
