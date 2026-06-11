"""Offline latency benchmark for the Agent 01 text-path graph.

Exercises the shared benchmark harness (packages/evals/benchmark.py) against the real graph on
the MOCK provider — a fully offline latency profile, no credentials, no network. This is a smoke
profile (does it run, are the percentiles well-formed), NOT an SLA gate: per DESIGN §1.5 the
real p50/p95 target is validated against live providers in Debug, and a hard wall-clock assertion
would be flaky in CI. The harness is what a live latency-tuning pass will reuse.
"""

from __future__ import annotations

import io

import yaml
from pathlib import Path

from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry
from evals.benchmark import BenchmarkResult, benchmark

from agent.graph import build_graph

_CFG_PATH = Path(__file__).parent.parent.parent / "config" / "base.yaml"


def _cfg() -> dict:
    return yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))


def _run_once_factory():
    cfg = _cfg()

    def run_once():
        llm = MockLLMProvider(default_scenario="pass")
        tel = StdoutTelemetry(service="bench", stream=io.StringIO())
        graph = build_graph(cfg, llm, tel)
        graph.invoke({"raw_input": "Machine learning is transforming healthcare diagnostics.",
                      "input_type": "text"})

    return run_once


def test_text_path_latency_benchmark_runs_offline():
    result = benchmark(_run_once_factory(), iterations=5, warmup=1, label="agent01.text_path")
    assert isinstance(result, BenchmarkResult)
    assert result.iterations == 5
    # Well-formed percentiles (no SLA assertion — see module docstring).
    assert result.min_ms <= result.p50_ms <= result.p95_ms <= result.p99_ms <= result.max_ms
    assert result.p95_ms > 0.0


def test_benchmark_report_is_serializable():
    result = benchmark(_run_once_factory(), iterations=3, label="agent01.text_path")
    # The report round-trips (usable as a CI artifact / tracked baseline).
    restored = BenchmarkResult.model_validate_json(result.model_dump_json())
    assert restored == result
