"""Integration test: full graph end-to-end on offline mocks (generated skeleton).

Proves the inherited platform guarantees: terminal status + cost under ceiling, pre-call budget
block (provider NOT called), and billed-cost preservation on a provider failure.
"""
from __future__ import annotations

import copy

from core.interfaces import BillableProviderError, LLMResponse
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.graph import build_graph
from agent.schemas import ReportWriterPackage

_CFG = {
    "provider": "mock",
    "service": "agent-02-report-writer",
    "llm": {"provider": "mock", "tier_models": {"cheap": "mock/cheap", "strong": "mock/strong"}},
    "cost": {
        "ceiling_inr": 50.0,
        "is_mock": True,
        "provider_currency": "USD",
        "fx_rates": {"USD": 83.0},
        "estimated_stage_cost_inr": {"process": 12.0},
        "output_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
        "input_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
        "fixed_cost_inr": {"cheap": 0.0, "strong": 0.0},
        "max_prompt_tokens": {"cheap": 16384, "strong": 32768},
    },
    "graph": {"max_revision_cycles": 2},
}


def _tel():
    return StdoutTelemetry(service="test")


class _CountingLLM(MockLLMProvider):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = 0

    def respond(self, messages, **kwargs):
        self.calls += 1
        return super().respond(messages, **kwargs)


class _BillingFailLLM:
    """A provider that fails AFTER (potentially) billing — carries non-zero usage cost."""

    name = "billing-fail"

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        raise BillableProviderError(
            Usage(prompt_tokens=10, completion_tokens=5, cost_native=0.1, currency="USD", synthetic=False),
            "provider_call_failed",
        )


class _PricedSuccessLLM:
    """A successful provider call with non-zero cost, used to test later failures."""

    name = "priced-success"

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        return LLMResponse(
            text="ok",
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=5,
                cost_native=0.1,
                currency="USD",
                synthetic=False,
            ),
        )


class _ExitRaisingContext:
    def __init__(self, inner, *, always=False):
        self._inner = inner
        self._always = always

    def __enter__(self):
        return self._inner.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self._inner.__exit__(exc_type, exc_value, traceback)
        if exc_type is None or self._always:
            raise RuntimeError("intentional process span-exit failure")
        return False


class _SpanExitRaisingTelemetry(StdoutTelemetry):
    def span(self, name, **attrs):
        base = super().span(name, **attrs)
        return _ExitRaisingContext(base) if name == "process" else base


class _AlwaysExitRaisingTelemetry(StdoutTelemetry):
    def span(self, name, **attrs):
        base = super().span(name, **attrs)
        return _ExitRaisingContext(base, always=True) if name == "process" else base


def test_text_path_reaches_terminal_status():
    pkg = build_graph(_CFG, MockLLMProvider(default_scenario="pass"), _tel()).invoke(
        {"raw_input": "hello world", "input_type": "text"}
    )["final_output"]
    assert isinstance(pkg, ReportWriterPackage)
    assert pkg.status in ("pass", "needs_human", "stopped_cost_ceiling", "error")
    assert pkg.cost.total_inr < 50.0


def test_blank_input_routes_to_error():
    pkg = build_graph(_CFG, MockLLMProvider(default_scenario="pass"), _tel()).invoke(
        {"raw_input": "", "input_type": "text"}
    )["final_output"]
    assert pkg.status == "error"


def test_budget_block_stops_before_provider_call():
    cfg = copy.deepcopy(_CFG)
    cfg["cost"]["max_prompt_tokens"] = {"cheap": 1, "strong": 1}  # any real prompt exceeds -> block
    llm = _CountingLLM(default_scenario="pass")
    pkg = build_graph(cfg, llm, _tel()).invoke(
        {"raw_input": "hello world", "input_type": "text"}
    )["final_output"]
    assert pkg.status == "stopped_cost_ceiling"
    assert llm.calls == 0  # provider MUST NOT be called when budget authorization fails


def test_billable_failure_preserves_cost():
    pkg = build_graph(_CFG, _BillingFailLLM(), _tel()).invoke(
        {"raw_input": "hello world", "input_type": "text"}
    )["final_output"]
    assert pkg.status == "error"
    assert pkg.cost.total_inr > 0.0  # incurred cost preserved despite the failure


def test_span_exit_failure_after_billable_call_preserves_cost():
    pkg = build_graph(
        _CFG,
        _PricedSuccessLLM(),
        _SpanExitRaisingTelemetry(service="test"),
    ).invoke({"raw_input": "hello world", "input_type": "text"})["final_output"]
    assert pkg.status == "error"
    assert pkg.cost.total_inr > 0.0
    assert {stage.stage for stage in pkg.cost.stage_costs} == {"process"}


def test_provider_failure_plus_span_exit_failure_preserves_cost():
    pkg = build_graph(
        _CFG,
        _BillingFailLLM(),
        _AlwaysExitRaisingTelemetry(service="test"),
    ).invoke({"raw_input": "hello world", "input_type": "text"})["final_output"]
    assert pkg.status == "error"
    assert pkg.cost.total_inr > 0.0
    assert {stage.stage for stage in pkg.cost.stage_costs} == {"process"}
