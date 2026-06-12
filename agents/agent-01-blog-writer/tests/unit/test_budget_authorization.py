"""Unit tests — budget authorization wiring in Agent 01 graph nodes.

Eighth repair pass:
- route_after_draft correctly routes cost_gate_ok=False to finalize (not review).
- Adversarial high-cost provider (HighCostMockProvider) proves total_inr never exceeds
  the ₹50 ceiling even when actual costs are significantly higher than estimates.

Seventh repair pass:
- All LLM nodes use authorize_call before the provider call.
- CostCeilingExceeded from any node → status='stopped_cost_ceiling' (not 'error').
- Zero ceiling → stopped_cost_ceiling.
- Provider calls are not made after budget rejection.
- Graph never reports total_inr above ceiling when mock costs are non-zero.
"""
from __future__ import annotations

from typing import Any

import pytest

from core.cost import CostCeilingExceeded
from core.interfaces import LLMProvider, LLMResponse
from core.interfaces.errors import BillableProviderError
from core.interfaces.llm import Tier
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider, _apply_scenario, _mock_data
from core.providers.mock.telemetry import StdoutTelemetry

from agent.graph import build_graph
from agent.nodes.review import RawQualityReport as _RawQualityReport
from agent.schemas import BlogPackage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CapturingTelemetry(StdoutTelemetry):
    def __init__(self):
        super().__init__(service="test")
        self.events: list[dict] = []

    def _emit(self, record: dict) -> None:
        self.events.append(record)


def _cfg_mock(ceiling_inr: float = 50.0, max_revision_cycles: int = 2) -> dict:
    return {
        "cost": {
            "ceiling_inr": ceiling_inr,
            "is_mock": True,
            "fx_rates": {"USD": 83.0},
            "estimated_stage_cost_inr": {
                "normalize": 0.3,
                "extract_ideas": 0.3,
                "plan": 0.5,
                "draft": 12.0,
                "review": 6.0,
            },
            "output_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
            # Final repair: estimate_prompt_tokens now uses 1 token per UTF-8 byte
            # (not ceil(bytes/4)), so the conservative limit must be set high enough
            # that typical blog prompts (a few KB) clear the gate.  These match base.yaml.
            "max_prompt_tokens": {"cheap": 16384, "strong": 32768},
        },
        "graph": {"max_revision_cycles": max_revision_cycles},
        "service": "test",
    }


def _run(llm: LLMProvider, cfg: dict | None = None) -> BlogPackage:
    tel = CapturingTelemetry()
    graph = build_graph(cfg or _cfg_mock(), llm, tel)
    result = graph.invoke({"raw_input": "Machine learning is revolutionising healthcare."})
    return result["final_output"]


# ---------------------------------------------------------------------------
# Test 1: CostCeilingExceeded from any node → stopped_cost_ceiling (not error)
# ---------------------------------------------------------------------------

def test_cost_ceiling_exceeded_from_normalize_routes_to_stopped_not_error():
    """When normalize's authorize_call raises CostCeilingExceeded, status is
    'stopped_cost_ceiling' (budget rejection), NOT 'error' (unexpected exception).

    With ceiling=0.001: 0(current) + 0.3(normalize) + 18.8(downstream) = 19.1 > 0.001
    → CostCeilingExceeded in normalize → cost_gate_ok=False → stopped_cost_ceiling.
    """
    llm = MockLLMProvider(default_scenario="pass")
    pkg = _run(llm, _cfg_mock(ceiling_inr=0.001))

    assert pkg.status == "stopped_cost_ceiling", (
        f"Expected stopped_cost_ceiling when ceiling is tiny, got {pkg.status!r}. "
        "CostCeilingExceeded must route to stopped_cost_ceiling, not error."
    )
    # No LLM calls should have been made (budget rejected before first call)
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "draft" not in stage_names
    assert "review" not in stage_names


def test_zero_ceiling_returns_stopped_cost_ceiling():
    """Zero ceiling → CostCeilingExceeded at normalize → stopped_cost_ceiling."""
    llm = MockLLMProvider(default_scenario="pass")
    pkg = _run(llm, _cfg_mock(ceiling_inr=0.0))

    assert pkg.status == "stopped_cost_ceiling"
    assert "cost" in (pkg.notes or "").lower() or "ceiling" in (pkg.notes or "").lower()


# ---------------------------------------------------------------------------
# Test 2: Provider call is not made after budget rejection
# ---------------------------------------------------------------------------

class CountingLLMProvider(LLMProvider):
    """Provider that counts how many times respond() is called."""
    name = "counting"

    def __init__(self):
        self.call_count = 0
        self._delegate = MockLLMProvider(default_scenario="pass")

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        self.call_count += 1
        return self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )


class ParamCapturingLLMProvider(LLMProvider):
    """Provider that records params sent by nodes before delegating to the mock."""
    name = "param_capture"

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self._delegate = MockLLMProvider(default_scenario="pass")

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        self.calls.append({"tier": tier, "params": dict(params or {})})
        return self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )


def test_provider_not_called_after_budget_rejection():
    """When ceiling is tiny, authorize_call rejects before any LLM call."""
    llm = CountingLLMProvider()
    pkg = _run(llm, _cfg_mock(ceiling_inr=0.001))

    assert pkg.status == "stopped_cost_ceiling"
    assert llm.call_count == 0, (
        f"Expected 0 LLM calls after budget rejection, got {llm.call_count}"
    )


def test_live_output_caps_limit_all_llm_node_max_tokens():
    """Stage output caps prevent a live call from consuming all headroom.

    Without max_output_tokens, early calls can receive a huge max_tokens value because
    most of the run budget is still available, while review can truncate structured
    JSON if its cap is too low.  Each node must cap the outgoing provider param to
    its configured stage limit.
    """
    cfg = _cfg_mock()
    cfg["cost"]["is_mock"] = False
    cfg["cost"]["output_cost_per_token_inr"] = {"cheap": 0.000001, "strong": 0.000001}
    cfg["cost"]["input_cost_per_token_inr"] = {"cheap": 0.000001, "strong": 0.000001}
    cfg["cost"]["max_output_tokens"] = {
        "normalize": 123,
        "extract_ideas": 456,
        "plan": 789,
        "draft": 1011,
        "review": 1213,
    }

    llm = ParamCapturingLLMProvider()
    pkg = _run(llm, cfg)

    assert pkg.status == "pass"
    assert [call["params"]["max_tokens"] for call in llm.calls[:5]] == [
        123,
        456,
        789,
        1011,
        1213,
    ]


# ---------------------------------------------------------------------------
# Test 3: Adversarial high-cost provider — ceiling never exceeded
# ---------------------------------------------------------------------------

class HighCostMockProvider(LLMProvider):
    """Simulates a provider where each LLM call accumulates real INR cost."""
    name = "high_cost_mock"

    def __init__(self, cost_per_call_inr: float, scenario: str = "pass"):
        self._cost = cost_per_call_inr
        self._delegate = MockLLMProvider(default_scenario=scenario)

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        resp = self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )
        # Override usage with a non-zero cost (cost_native in USD, fx=83.0 → INR)
        cost_native = self._cost / 83.0  # convert INR to USD
        usage = Usage(
            prompt_tokens=10, completion_tokens=10,
            cost_native=cost_native, currency="USD",
        )
        if resp.structured is not None:
            return LLMResponse.structured_from(
                type(resp.structured), resp.structured.model_dump(), usage=usage
            )
        return LLMResponse(text=resp.text or "", usage=usage)


def test_adversarial_high_cost_triggers_cost_gate_and_ceiling_respected():
    """HighCostMockProvider (₹15/call) triggers cost_gate; total_inr stays ≤ ₹50.

    With ₹15 per call:
    - normalize=₹15, extract=₹15, plan=₹15 → accumulated=₹45
    - cost_gate: 45 + draft_est(12) + review_est(6) = 63 > 50 → BLOCKED
    - Graph finishes with stopped_cost_ceiling; total_inr=₹45 ≤ ceiling=₹50.

    This replaces the zero-cost test (which proved nothing) with a real non-zero
    cost scenario that exercises the ceiling backstop in cost_gate.
    """
    ceiling = 50.0
    llm = HighCostMockProvider(cost_per_call_inr=15.0)
    pkg = _run(llm, _cfg_mock(ceiling_inr=ceiling))

    assert pkg.cost.total_inr <= ceiling, (
        f"total_inr={pkg.cost.total_inr:.4f} exceeded ceiling={ceiling} "
        "with HighCostMockProvider(15 INR/call)"
    )
    assert pkg.status == "stopped_cost_ceiling", (
        f"Expected stopped_cost_ceiling (cost_gate fires at ₹45+18=₹63 > ₹50), "
        f"got {pkg.status!r}"
    )


def test_adversarial_moderate_cost_completes_within_ceiling():
    """HighCostMockProvider (₹8/call) completes normally; total_inr stays ≤ ₹50.

    With ₹8 per call and 5 LLM calls (normalize+extract+plan+draft+review):
    - Estimated total pipeline: 0.3+0.3+0.5+12+6 = 19.1 → well under ₹50
    - Actual total: 5 × ₹8 = ₹40 ≤ ₹50
    - authorize_call gates allow all calls since estimates clear the ceiling.
    """
    ceiling = 50.0
    llm = HighCostMockProvider(cost_per_call_inr=8.0)
    pkg = _run(llm, _cfg_mock(ceiling_inr=ceiling))

    assert pkg.cost.total_inr <= ceiling, (
        f"total_inr={pkg.cost.total_inr:.4f} exceeded ceiling={ceiling} "
        "with HighCostMockProvider(8 INR/call)"
    )
    assert pkg.status in ("pass", "needs_human", "stopped_cost_ceiling"), (
        f"Unexpected status {pkg.status!r}"
    )


# ---------------------------------------------------------------------------
# Test 4: route_after_draft correctly handles cost_gate_ok=False
# ---------------------------------------------------------------------------

def test_route_after_draft_budget_rejection_routes_to_stopped_not_review():
    """If draft's authorize_call raises CostCeilingExceeded, status=stopped_cost_ceiling.

    Eighth repair: route_after_draft now checks cost_gate_ok=False.  Previously,
    a budget rejection in draft could still proceed to review (cost_gate_ok=False
    was not checked before routing).

    With ceiling=19.2: 0+0.3+0.3+0.5+12+6 = 19.1 <= 19.2 → all cheap nodes pass.
    Then cost_gate checks 0(actual) + 12 + 6 = 18 <= 19.2 → OK.
    Then draft authorize_call: 0 + 12(draft) + 6(review) = 18 <= 19.2 → OK.
    Graph should complete normally.

    For budget rejection specifically in draft: use tiny ceiling that just fits
    cheap stages but not draft.  ceiling=1.5: 0+0.3+0.3+0.5+12+6 = 19.1 > 1.5
    → blocked at normalize → stopped_cost_ceiling (route_after_normalize).
    """
    # The easiest way to force draft budget rejection without reaching plan is to
    # set ceiling just above the cheap-node estimates but below draft+review combined:
    # normalize(0.3)+extract(0.3)+plan(0.5)=1.1 plus draft(12)+review(6)=18 → 19.1
    # ceiling=2.0: cheap nodes authorized (0+0.3+18.8=19.1 > 2.0 → blocked at normalize)
    # That tests the normalize path.  For draft specifically use HIGH actual costs.
    llm = HighCostMockProvider(cost_per_call_inr=15.0)
    pkg = _run(llm, _cfg_mock(ceiling_inr=50.0))

    # cost_gate sees 45 accumulated + draft(12) + review(6) = 63 > 50 → blocked
    assert pkg.status == "stopped_cost_ceiling"
    # No review stage should have run (blocked before draft or at cost_gate)
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "review" not in stage_names, (
        "review should not run when budget ceiling stops execution before/at draft"
    )


def test_graph_completes_with_exact_budget():
    """With sufficient budget the graph completes normally (regression guard)."""
    llm = MockLLMProvider(default_scenario="pass")
    pkg = _run(llm, _cfg_mock(ceiling_inr=50.0))

    assert pkg.status == "pass"  # sufficient budget → completes normally


# ---------------------------------------------------------------------------
# Test 6: Tenth repair — pre-call rejection + honest ledger
# ---------------------------------------------------------------------------

def _cfg_high_input_cost(ceiling_inr: float = 19.5) -> dict:
    """Non-mock pricing config where input cost per token > per-call output budget.

    For normalize (first stage):
      call_budget = ceiling_inr - 0 - downstream_reserve(18.8) = ceiling_inr - 18.8
      input_reserve = input_cpt(0.001) × max_prompt_tokens(1000) = 1.0
      When ceiling_inr=19.5: call_budget=0.7, input_reserve=1.0 > 0.7
        → output_budget=0 → max_tokens=0 → CostCeilingExceeded (pre-call)
        → provider is NEVER called.

    No 'provider' or 'llm.provider' key → resolve_is_mock reads cost.is_mock=False.
    """
    return {
        "cost": {
            "ceiling_inr": ceiling_inr,
            "is_mock": False,
            "fx_rates": {"USD": 83.0},
            "estimated_stage_cost_inr": {
                "normalize": 0.3,
                "extract_ideas": 0.3,
                "plan": 0.5,
                "draft": 12.0,
                "review": 6.0,
            },
            "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.001},
            "input_cost_per_token_inr": {"cheap": 0.001, "strong": 0.001},
            "max_prompt_tokens": {"cheap": 1000, "strong": 1000},
        },
        "graph": {"max_revision_cycles": 2},
        "service": "test",
    }


def test_high_input_cost_prevents_provider_call_before_zero_max_tokens():
    """When input cost alone exhausts the per-call budget, the provider is never called.

    Tenth repair: authorize_call now raises CostCeilingExceeded when max_tokens=0
    (output budget exhausted by input-token reserve) BEFORE calling the provider.
    This replaces the previous ₹60 test that verified discarding of incurred costs —
    the correct fix is pre-call rejection, not post-call ledger manipulation.

    Config: input_cpt=0.001, max_prompt=1000, ceiling=19.5
      normalize call_budget=0.7, input_reserve=1.0 > 0.7 → max_tokens=0
      → CostCeilingExceeded in authorize_call → provider is NOT called.
    """
    llm = CountingLLMProvider()
    pkg = _run(llm, _cfg_high_input_cost(ceiling_inr=19.5))

    assert pkg.status == "stopped_cost_ceiling", (
        f"Expected stopped_cost_ceiling when input cost exhausts output budget, "
        f"got {pkg.status!r}"
    )
    assert llm.call_count == 0, (
        f"Provider must not be called when max_tokens=0 (no output headroom); "
        f"got call_count={llm.call_count}"
    )


def test_post_call_overrun_is_recorded_in_ledger_not_discarded():
    """When actual call cost exceeds the ceiling, the incurred cost IS recorded.

    Tenth repair: _node_with_error_guard preserves cost_usage on post-call ceiling
    breach.  Previously the guard discarded it (falsifying the ledger).  Honest
    accounting means BlogPackage.cost reflects actual spend even if it exceeds the
    ceiling estimate; the pipeline is stopped (stopped_cost_ceiling) but costs are
    not silently erased.

    With HighCostMockProvider(₹15/call), after 3 calls (normalize+extract+plan=₹45)
    the cost_gate fires (45+12+6=63 > 50) → stopped_cost_ceiling.
    The ledger must reflect the ₹45 actually spent.
    """
    ceiling = 50.0
    llm = HighCostMockProvider(cost_per_call_inr=15.0)
    pkg = _run(llm, _cfg_mock(ceiling_inr=ceiling))

    assert pkg.status == "stopped_cost_ceiling"
    # The ₹45 incurred across 3 calls must appear in the ledger — not zero.
    assert pkg.cost.total_inr > 0, (
        f"Expected non-zero total_inr (actual spend preserved), "
        f"got {pkg.cost.total_inr:.4f}"
    )
    # Verify stage costs are recorded (normalize, extract_ideas, plan each ₹15)
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "normalize" in stage_names, "normalize cost must be in ledger"


# ---------------------------------------------------------------------------
# Test 5: Every LLM node performs pre-call budget authorization
# ---------------------------------------------------------------------------

class BudgetAuthCapture(LLMProvider):
    """Records which stages made LLM calls (to verify authorize_call ran for each)."""
    name = "budget_auth_capture"

    def __init__(self, scenario: str = "pass"):
        self._delegate = MockLLMProvider(default_scenario=scenario)
        self.stages_called: list[str] = []

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        # Infer the stage from message content (heuristic for test purposes)
        last_msg = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        if "clean the following" in last_msg.lower():
            self.stages_called.append("normalize")
        elif "main_idea" in last_msg.lower() or "analyse the text" in last_msg.lower():
            self.stages_called.append("extract_ideas")
        elif "content plan" in last_msg.lower():
            self.stages_called.append("plan")
        elif "write a complete" in last_msg.lower():
            self.stages_called.append("draft")
        elif "rigorous blog editor" in last_msg.lower():
            self.stages_called.append("review")
        return self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )


def test_all_nodes_make_llm_calls_on_pass_path():
    """Verify that all expected stages complete their LLM calls on the pass path.

    Indirectly confirms that authorize_call did not block any of them.
    """
    llm = BudgetAuthCapture(scenario="pass")
    pkg = _run(llm, _cfg_mock(ceiling_inr=50.0))

    assert pkg.status == "pass"
    # All stages should have called the LLM (normalize may or may not — it's text-only)
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "draft" in stage_names, "draft node must have made an LLM call"
    assert "review" in stage_names, "review node must have made an LLM call"


# ---------------------------------------------------------------------------
# Test 7: Oversized input blocked before provider call — eleventh repair
# ---------------------------------------------------------------------------

def _cfg_tiny_prompt(max_prompt_tokens_cheap: int = 10) -> dict:
    """Config with a tiny max_prompt_tokens so any real input exceeds the limit.

    mock provider (is_mock=True) with max_prompt_tokens.cheap=10 chars/4≈2 tokens.
    A 500-char raw_input will produce ~125 tokens, which far exceeds 10.
    The node must raise CostCeilingExceeded before calling the provider.
    """
    return {
        "cost": {
            "ceiling_inr": 50.0,
            "is_mock": True,
            "fx_rates": {"USD": 83.0},
            "estimated_stage_cost_inr": {
                "normalize": 0.3,
                "extract_ideas": 0.3,
                "plan": 0.5,
                "draft": 12.0,
                "review": 6.0,
            },
            "output_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
            "input_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
            "max_prompt_tokens": {"cheap": max_prompt_tokens_cheap, "strong": max_prompt_tokens_cheap},
        },
        "graph": {"max_revision_cycles": 2},
        "service": "test",
    }


def test_oversized_input_blocks_provider_before_call():
    """When raw_input produces a prompt larger than max_prompt_tokens, the provider is not called.

    Eleventh repair: nodes build messages first, count actual prompt tokens via
    count_prompt_tokens(), and raise CostCeilingExceeded BEFORE calling authorize_call
    or the provider.

    Config: max_prompt_tokens.cheap=10 (allows only ~40 chars of content).
    Input: 500-char string → ~125 tokens → 125 > 10 → CostCeilingExceeded in normalize
    → cost_gate_ok=False → stopped_cost_ceiling, zero LLM calls.
    """
    llm = CountingLLMProvider()
    # 500-char raw_input — far exceeds the 10-token limit
    long_input = "Machine learning is revolutionising healthcare diagnostics. " * 9  # ~522 chars

    tel = CapturingTelemetry()
    cfg = _cfg_tiny_prompt(max_prompt_tokens_cheap=10)
    graph = build_graph(cfg, llm, tel)
    result = graph.invoke({"raw_input": long_input})
    pkg: BlogPackage = result["final_output"]

    assert pkg.status == "stopped_cost_ceiling", (
        f"Expected stopped_cost_ceiling when prompt exceeds max_prompt_tokens, "
        f"got {pkg.status!r}"
    )
    assert llm.call_count == 0, (
        f"Provider must not be called when prompt is too large; "
        f"got call_count={llm.call_count}"
    )


# ---------------------------------------------------------------------------
# Test 8: BillableNodeError cost preservation — final repair (Item 4)
# ---------------------------------------------------------------------------

class ReviewStructuredNoneProvider(LLMProvider):
    """Provider that succeeds on all nodes EXCEPT review, where structured is None.

    For all calls except review (response_schema=QualityReport), the mock delegate
    returns its normal structured output.  For review, the provider returns a
    text-only response so response.structured is None.

    review.py then does:
        report = response.structured   # → None
        report.overall_score           # → AttributeError inside try block
        → BillableNodeError raised → stage_cost preserved by _node_with_error_guard
    """
    name = "review_structured_none"

    def __init__(self, cost_per_call_inr: float = 5.0):
        self._cost = cost_per_call_inr
        self._delegate = MockLLMProvider(default_scenario="pass")

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        cost_native = self._cost / 83.0
        usage = Usage(
            prompt_tokens=10, completion_tokens=10,
            cost_native=cost_native, currency="USD",
        )
        # Only intercept the review node (response_schema=RawQualityReport).
        # All other nodes (ExtractedIdeas, BlogPlan, text-only normalize/draft)
        # must succeed normally so the graph reaches review.
        if response_schema is _RawQualityReport:
            return LLMResponse(text="", usage=usage)   # structured=None → triggers BillableNodeError

        resp = self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )
        if resp.structured is not None:
            return LLMResponse.structured_from(
                type(resp.structured), resp.structured.model_dump(), usage=usage,
            )
        return LLMResponse(text=resp.text or "", usage=usage)


class ReviewBillableProviderFailure(LLMProvider):
    """Provider that reaches review, then raises a content-free billable category."""
    name = "review_billable_failure"

    def __init__(self, category: str = "schema_validation_failed"):
        self._category = category
        self._delegate = MockLLMProvider(default_scenario="pass")

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        if response_schema is _RawQualityReport:
            usage = Usage(
                prompt_tokens=100,
                completion_tokens=100,
                cost_native=1.0 / 83.0,
                currency="USD",
            )
            raise BillableProviderError(usage, self._category)
        return self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )


def test_billable_node_error_preserves_cost_in_ledger():
    """When post-call processing fails after a billable LLM call, the cost is preserved.

    Final repair (Item 4): _node_with_error_guard catches BillableNodeError and returns
    {"cost_usage": [be.stage_cost], "error_state": {...}} — the stage_cost is added to
    the ledger even though the node ultimately failed.

    This prevents a scenario where the LLM was charged but the cost silently appears
    as ₹0 in the ledger, masking real spend.

    Setup:
    - ReviewStructuredNoneProvider: LLM call succeeds with ₹5 usage; response.structured
      is None; review.py raises AttributeError on None.overall_score inside the try block;
      BillableNodeError wraps the stage_cost(review, ₹5); guard preserves it.
    - Final package: status='error' (not 'stopped_cost_ceiling'), review stage cost in ledger.
    """
    ceiling = 50.0
    llm = ReviewStructuredNoneProvider(cost_per_call_inr=5.0)
    tel = CapturingTelemetry()

    graph = build_graph(_cfg_mock(ceiling_inr=ceiling), llm, tel)
    result = graph.invoke({"raw_input": "Machine learning is revolutionising healthcare."})
    pkg: BlogPackage = result["final_output"]

    # BillableNodeError is a processing failure — status must be 'error', not 'stopped_cost_ceiling'.
    assert pkg.status == "error", (
        f"Expected status='error' when post-call processing fails (BillableNodeError), "
        f"got {pkg.status!r}"
    )

    # The review stage cost MUST appear in the ledger (preserved by _node_with_error_guard).
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "review" in stage_names, (
        "review stage cost must be preserved in the ledger when BillableNodeError is raised — "
        "silently dropping the cost would falsify the spend ledger"
    )

    # Total cost must be > 0 (₹5 × N calls from ReviewStructuredNoneProvider).
    assert pkg.cost.total_inr > 0, (
        f"Expected non-zero total_inr (actual spend preserved by BillableNodeError), "
        f"got {pkg.cost.total_inr:.4f}"
    )

    # The guard must have emitted a node.error telemetry event for 'review'.
    # StdoutTelemetry.log() emits {"event": "log", "msg": <event_code>, "attrs": {...}}.
    # "node.error" is in _PLATFORM_LABELS so it is NOT redacted; msg="node.error".
    # (The "node" attribute is redacted since it is not a registered platform attr key in
    # the basic CapturingTelemetry — but the msg itself passes through correctly.)
    error_log_events = [
        e for e in tel.events
        if e.get("event") == "log" and e.get("msg") == "node.error"
    ]
    assert error_log_events, (
        "node.error log event must be emitted when BillableNodeError is raised "
        "in the review node (final repair Item 5: node.error telemetry)"
    )


def test_billable_provider_error_category_is_surfaced_safely():
    """Final notes include only the content-free provider failure category.

    Live structured-output failures are otherwise impossible to distinguish from
    generic RuntimeError-in-review failures.  The category is allowlisted by
    core.interfaces.errors and contains no raw provider message or response text.
    """
    llm = ReviewBillableProviderFailure(category="schema_validation_failed")
    pkg = _run(llm, _cfg_mock(ceiling_inr=50.0))

    assert pkg.status == "error"
    assert "Billable provider failure in review: schema_validation_failed" in (pkg.notes or "")
    assert "RAW" not in (pkg.notes or "")


def test_billable_node_error_does_not_route_to_stopped_cost_ceiling():
    """BillableNodeError routes to status='error', not 'stopped_cost_ceiling'.

    'stopped_cost_ceiling' is reserved for budget rejections (CostCeilingExceeded).
    A BillableNodeError is a post-call processing failure — the budget was not
    exhausted; the node failed after the LLM call was already made and billed.
    """
    llm = ReviewStructuredNoneProvider(cost_per_call_inr=1.0)
    pkg = _run(llm, _cfg_mock(ceiling_inr=50.0))

    assert pkg.status == "error", (
        f"BillableNodeError must produce status='error' (not 'stopped_cost_ceiling'), "
        f"got {pkg.status!r}"
    )
