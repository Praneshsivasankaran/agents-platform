"""Integration tests — Agent 01 full text-path graph on mock providers (DESIGN §1, §9).

Runs the complete LangGraph StateGraph end-to-end using offline mocks only (no credentials,
no network).  Each test scenario exercises a different terminal path:

  test_pass_path              — clean text, passes on first review
  test_needs_human_path       — hard-fail flag, escalated immediately
  test_thin_input_path        — usable=False from extract_ideas, short-circuits
  test_stopped_cost_ceiling   — ceiling_inr=0 so cost gate fires before draft
  test_revise_then_pass_path  — first review returns revise, second passes
  test_hard_fail_flags_accumulate — two revision cycles, each adds a flag; both must survive
  test_invalid_raw_input       — empty raw_input → status=error from intake node

Repair (Increment 3):
- result["final_output"] (was final_package)
- pkg.full_draft (was body_markdown)
- pkg.quality    (was quality_report)
- pkg.cost       (was cost_usage)
- pkg.notes      (was error_message)
- pkg.revision_count (was revision_cycles_used; semantics change: counts completed revisions)
- MultiFlagMock QualityReport includes consistent sub_scores (sum must equal overall_score)
- Config includes revise_draft + revise_review stages (for cost_gate combined check)

These tests act as the wiring/contract gate: they prove that every node runs, the
accumulator reducers work end-to-end, cost telemetry is produced, and every terminal
``BlogPackage.status`` is reachable.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from core.interfaces import BillableProviderError, LLMProvider, LLMResponse, Telemetry
from core.interfaces.llm import Tier
from core.interfaces.usage import Usage
from core.providers.mock.llm import (
    MockLLMProvider,
    _apply_scenario,
    _mock_data,
)
from core.providers.mock.telemetry import StdoutTelemetry

from agent.graph import build_graph
from agent.schemas import BlogPackage


# ---------------------------------------------------------------------------
# Helpers — lightweight telemetry sink that captures events for assertions
# ---------------------------------------------------------------------------

class CapturingTelemetry(StdoutTelemetry):
    """StdoutTelemetry subclass that also appends every emitted record to a list."""

    def __init__(self):
        super().__init__(service="test")
        self.events: list[dict] = []

    def _emit(self, record: dict) -> None:  # type: ignore[override]
        self.events.append(record)
        # Don't call super()._emit so tests stay silent


# ---------------------------------------------------------------------------
# SequenceMockLLMProvider — for revise-then-pass tests
# ---------------------------------------------------------------------------

class SequenceMockLLMProvider(LLMProvider):
    """Returns a pre-defined sequence of scenarios for structured calls.

    Each structured response pops one scenario from the front of ``schema_scenarios``.
    Text (non-schema) calls always use the ``text_scenario``.
    """

    name = "sequence_mock"

    def __init__(self, schema_scenarios: list[str], text_scenario: str = "pass") -> None:
        self._schema_scenarios = list(schema_scenarios)
        self._text_scenario = text_scenario
        self._schema_call_idx = 0

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        usage = Usage(synthetic=True)

        if response_schema is not None:
            if self._schema_call_idx < len(self._schema_scenarios):
                scenario = self._schema_scenarios[self._schema_call_idx]
            else:
                scenario = "pass"  # default once sequence is exhausted
            self._schema_call_idx += 1

            data = _mock_data(response_schema)
            data = _apply_scenario(data, scenario, schema=response_schema)
            return LLMResponse.structured_from(response_schema, data, usage=usage)

        text = f"[seq_mock:{tier}:{self._text_scenario}] mock draft body"
        return LLMResponse(text=text, usage=usage)


# ---------------------------------------------------------------------------
# CountingProvider — counts LLM calls (for zero-call assertions)
# ---------------------------------------------------------------------------

class CountingProvider(LLMProvider):
    """Provider that counts how many times respond() is called."""
    name = "counting"

    def __init__(self, scenario: str = "pass"):
        self.call_count = 0
        self._delegate = MockLLMProvider(default_scenario=scenario)

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        self.call_count += 1
        return self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )


# ---------------------------------------------------------------------------
# HighCostMockProvider — reports non-zero cost per call (for cost tests)
# ---------------------------------------------------------------------------

class HighCostMockProvider(LLMProvider):
    """Provider that reports a configurable INR cost per call via Usage."""
    name = "high_cost_mock"

    def __init__(self, cost_per_call_inr: float, scenario: str = "pass"):
        self._cost = cost_per_call_inr
        self._delegate = MockLLMProvider(default_scenario=scenario)

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        resp = self._delegate.respond(
            messages, tier=tier, params=params, tools=tools,
            response_schema=response_schema,
        )
        cost_native = self._cost / 83.0  # convert INR to USD (fx_rate=83)
        usage = Usage(
            prompt_tokens=10, completion_tokens=10,
            cost_native=cost_native, currency="USD",
        )
        if resp.structured is not None:
            return LLMResponse.structured_from(
                type(resp.structured), resp.structured.model_dump(), usage=usage,
            )
        return LLMResponse(text=resp.text or "", usage=usage)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _cfg(ceiling_inr: float = 50.0, max_revision_cycles: int = 2) -> dict:
    return {
        "cost": {
            "ceiling_inr": ceiling_inr,
            # Seventh repair: is_mock=True allows authorize_call to skip the fail-closed
            # zero-pricing check when output_cost_per_token_inr=0.0 (mock has no real pricing).
            "is_mock": True,
            "fx_rates": {"USD": 83.0},
            # Seventh repair: cheap-node estimates added so authorize_call can reserve
            # downstream budget in normalize, extract_ideas, and plan.
            "estimated_stage_cost_inr": {
                "normalize": 0.3,
                "extract_ideas": 0.3,
                "plan": 0.5,
                "draft": 12.0,
                "review": 6.0,
            },
            # output_cost_per_token_inr: 0 for mock (no per-token cap derived)
            "output_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
            # Final repair: estimate_prompt_tokens now uses 1 token per UTF-8 byte
            # (not ceil(bytes/4)).  Set limits high enough for typical mock prompts
            # (a few KB of system + user messages).  These match base.yaml.
            "max_prompt_tokens": {"cheap": 16384, "strong": 32768},
        },
        "graph": {"max_revision_cycles": max_revision_cycles},
        "service": "test",
    }


def _run(llm: LLMProvider, cfg: dict | None = None) -> BlogPackage:
    """Build the graph, invoke it with a standard input, return the BlogPackage."""
    tel = CapturingTelemetry()
    graph = build_graph(cfg or _cfg(), llm, tel)
    result = graph.invoke({"raw_input": "Machine learning is revolutionising healthcare."})
    return result["final_output"]  # Repair: was final_package


# ---------------------------------------------------------------------------
# Test 1: Pass path
# ---------------------------------------------------------------------------

def test_pass_path():
    """Clean text with mock scenario 'pass' → status='pass' with enrichment fields."""
    llm = MockLLMProvider(default_scenario="pass")
    pkg = _run(llm)

    assert pkg.status == "pass"
    assert pkg.title is not None
    assert pkg.full_draft is not None        # Repair: was body_markdown
    assert pkg.quality is not None           # Repair: was quality_report
    assert pkg.quality.pass_flag is True
    assert pkg.quality.overall_score >= 80
    assert len(pkg.hard_fail_flags) == 0
    assert pkg.cost.total_inr >= 0.0         # Repair: was cost_usage
    # draft and review StageCosts must be present; finalize is non-billable (no enrich stage)
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "draft" in stage_names
    assert "review" in stage_names
    # sixth repair: finalize derives enrichment from plan/draft data (no LLM call, no stage cost)
    assert "enrich" not in stage_names, (
        "finalize must NOT add an enrich StageCost — enrichment is derived without a billable call"
    )
    # Enrichment fields must still be non-empty for 'pass' (derived by _fallback_enrichment)
    assert pkg.alternative_titles, "alternative_titles must be non-empty for 'pass'"
    assert pkg.short_summary, "short_summary must be non-empty for 'pass'"
    assert pkg.seo_keywords, "seo_keywords must be non-empty for 'pass'"
    assert pkg.suggested_tags, "suggested_tags must be non-empty for 'pass' (sixth repair)"
    assert pkg.meta_description, "meta_description must be non-empty for 'pass'"


# ---------------------------------------------------------------------------
# Test 2: needs_human path (hard fail)
# ---------------------------------------------------------------------------

def test_needs_human_path():
    """Hard-fail scenario → status='needs_human'."""
    llm = MockLLMProvider(default_scenario="needs_human")
    pkg = _run(llm)

    assert pkg.status == "needs_human"
    assert pkg.notes is not None             # Repair: was error_message
    assert len(pkg.notes) > 0
    # Hard fail flags must be present (injection_followed is the mock's hard fail)
    assert len(pkg.hard_fail_flags) > 0


# ---------------------------------------------------------------------------
# Test 3: thin_input path
# ---------------------------------------------------------------------------

def test_thin_input_path():
    """usable=False from extract_ideas → graph short-circuits → status='needs_human'."""
    llm = MockLLMProvider(default_scenario="thin_input")
    pkg = _run(llm)

    assert pkg.status == "needs_human"
    assert pkg.notes is not None             # Repair: was error_message
    lower_notes = pkg.notes.lower()
    assert "thin" in lower_notes or "usable" in lower_notes or "2 extractable" in pkg.notes

    # Should NOT have run draft or review
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "draft" not in stage_names
    assert "review" not in stage_names


# ---------------------------------------------------------------------------
# Test 4: stopped_cost_ceiling path
# ---------------------------------------------------------------------------

def test_stopped_cost_ceiling_path():
    """Tiny ceiling → budget authorization fires before first LLM call → status='stopped_cost_ceiling'.

    seventh repair: authorize_call in normalize reserves all downstream stages
    (extract_ideas+plan+draft+review ≈ 19.1 INR).  With ceiling_inr=0.001:
      0 (current) + 0.3 (normalize) + 18.8 (downstream) = 19.1 > 0.001
    → CostCeilingExceeded → _node_with_error_guard returns cost_gate_ok=False
    → route_after_normalize routes to finalize → _determine_status → stopped_cost_ceiling.

    Note: with ceiling=0.001, CostCeilingExceeded fires at normalize (earlier than before);
    the terminal status and assertions are unchanged.
    """
    llm = MockLLMProvider(default_scenario="pass")
    cfg = _cfg(ceiling_inr=0.001)
    pkg = _run(llm, cfg)

    assert pkg.status == "stopped_cost_ceiling"
    assert pkg.notes is not None             # Repair: was error_message
    lower_notes = pkg.notes.lower()
    assert "cost" in lower_notes or "ceiling" in lower_notes

    # draft and review must NOT have run
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "draft" not in stage_names
    assert "review" not in stage_names


# ---------------------------------------------------------------------------
# Test 5: revise-then-pass path
# ---------------------------------------------------------------------------

def test_revise_then_pass_path():
    """First review returns 'revise', second returns 'pass' → status='pass', revision_count=1."""
    # Structured call sequence:
    #   1. ExtractedIdeas   → pass scenario (usable=True)
    #   2. BlogPlan         → pass scenario (valid plan)
    #   3. QualityReport    → revise (first review: low score, no hard fail)
    #   4. QualityReport    → pass  (second review: passes)
    # Text calls (normalize, draft) use "pass" scenario (irrelevant for routing).
    llm = SequenceMockLLMProvider(
        schema_scenarios=["pass", "pass", "revise", "pass"],
        text_scenario="pass",
    )
    pkg = _run(llm)

    assert pkg.status == "pass"
    # Repair: revision_count tracks completed revisions. Initial draft = 0, one revision = 1.
    assert pkg.revision_count == 1          # was revision_cycles_used == 2
    assert pkg.quality is not None          # Repair: was quality_report
    assert pkg.quality.pass_flag is True
    # Two draft StageCosts + two review StageCosts; no enrich (sixth repair: non-billable)
    stage_costs_by_name: list[str] = [sc.stage for sc in pkg.cost.stage_costs]
    assert stage_costs_by_name.count("draft") == 2
    assert stage_costs_by_name.count("review") == 2
    assert stage_costs_by_name.count("enrich") == 0, (
        "enrich must NOT be in stage_costs (sixth repair: enrichment is non-billable)"
    )
    # Enrichment must still be populated (derived by _fallback_enrichment)
    assert pkg.alternative_titles


# ---------------------------------------------------------------------------
# Test 6: hard_fail_flags flow end-to-end into BlogPackage
# ---------------------------------------------------------------------------

def test_hard_fail_flags_flow_into_package():
    """Multiple hard-fail flags from one review cycle all appear in the final package.

    The operator.add accumulator is tested at the unit level (test_state.py).  This test
    verifies the end-to-end wiring: the review node emits flags, LangGraph's accumulator
    merges them, and finalize writes them all into BlogPackage.hard_fail_flags.
    """
    class MultiFlagMock(LLMProvider):
        """Review returns two hard-fail flags in one cycle."""
        name = "multi_flag"

        def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
            from core.providers.mock.llm import _apply_scenario, _mock_data
            usage = Usage(synthetic=True)
            if response_schema is None:
                return LLMResponse(text="[multi_flag] draft body", usage=usage)

            from agent.schemas import QualityReport, SubScores
            if response_schema is QualityReport:
                # Repair: sub_scores must sum to overall_score (schema validator)
                ss = SubScores(
                    structure_flow=3, clarity_readability=3, idea_coverage=4,
                    originality=3, tone_audience_fit=3, seo_usefulness=3,
                    factual_safety_sources=3, grammar_polish=2, engagement_value=2,
                )  # sum = 26
                data = dict(
                    sub_scores=ss,
                    overall_score=26,
                    pass_flag=False,
                    needs_human=True,
                    hard_fail_flags=("injection_followed", "harmful_content"),
                    revision_notes="Multiple critical issues.",
                )
                return LLMResponse.structured_from(response_schema, data, usage=usage)

            # All other schemas: pass scenario
            data = _mock_data(response_schema)
            data = _apply_scenario(data, "pass", schema=response_schema)
            return LLMResponse.structured_from(response_schema, data, usage=usage)

    pkg = _run(MultiFlagMock())

    assert pkg.status == "needs_human"
    # Both flags from the single review must appear in the final package
    assert "injection_followed" in pkg.hard_fail_flags, (
        f"injection_followed missing from {pkg.hard_fail_flags}"
    )
    assert "harmful_content" in pkg.hard_fail_flags, (
        f"harmful_content missing from {pkg.hard_fail_flags}"
    )


def test_retriable_fail_then_pass():
    """Retriable hard-fail (poor_structure) on first review → revision → second review passes.

    This is the key regression test for Issue #3 (accumulated flags break pass):
    - First review returns poor_structure (retriable) → graph routes to draft revision.
    - poor_structure is accumulated into state["hard_fail_flags"] via operator.add.
    - Second review returns 'pass' (pass_flag=True, no flags).
    - finalize must use () for hard_fail_flags (not the accumulated state flags) so
      the BlogPackage with status='pass' validates successfully.
    - Without the Issue #3 fix, finalize would include poor_structure from state in the
      'pass' package, causing _passed_package_invariants to raise → _safe_finalize_wrapper
      catches → returns status='error' instead of 'pass'.
    """
    # Structured call sequence:
    #   1. ExtractedIdeas    → pass scenario (usable=True)
    #   2. BlogPlan          → pass scenario (valid plan)
    #   3. QualityReport     → retriable_fail (poor_structure flag, needs_human=False)
    #   4. QualityReport     → pass (second review: passes, no flags)
    # sixth repair: no 5th BlogEnrichment schema call — finalize derives enrichment from
    # plan/draft data without any LLM call.
    llm = SequenceMockLLMProvider(
        schema_scenarios=["pass", "pass", "retriable_fail", "pass"],
        text_scenario="pass",
    )
    pkg = _run(llm)

    assert pkg.status == "pass", (
        f"Expected status='pass' after retriable_fail → revision → pass, got {pkg.status!r}. "
        "This indicates Issue #3 (accumulated flags break pass) is not fixed: finalize likely "
        "included the historical 'poor_structure' flag in the passed package."
    )
    # Hard fail flags must be empty in a passed package — no historical retriable flags
    assert len(pkg.hard_fail_flags) == 0, (
        f"Passed package must have no hard_fail_flags; got {pkg.hard_fail_flags}"
    )
    # Enrichment must be present (from the fifth repair)
    assert pkg.alternative_titles, "alternative_titles must be populated for 'pass'"
    assert pkg.meta_description, "meta_description must be populated for 'pass'"
    # revision_count should be 1 (one revision cycle completed)
    assert pkg.revision_count == 1, (
        f"Expected revision_count=1 after one revision; got {pkg.revision_count}"
    )


def test_hard_fail_flags_revise_then_hard_fail():
    """First review: low score, no hard fail (revision).  Second review: hard fail → package.

    This is the primary accumulation scenario in the current routing design: flags are only
    produced in the TERMINAL review (since any hard_fail → finalize immediately).  The
    operator.add reducer ensures those flags survive into BlogPackage unchanged.
    """
    llm = SequenceMockLLMProvider(
        schema_scenarios=["pass", "pass", "revise", "needs_human"],
        text_scenario="pass",
    )
    pkg = _run(llm)

    assert pkg.status == "needs_human"
    # Second review (needs_human scenario) produces injection_followed flag
    assert "injection_followed" in pkg.hard_fail_flags


# ---------------------------------------------------------------------------
# Test 7: invalid raw_input → error path from intake
# ---------------------------------------------------------------------------

def test_invalid_raw_input_empty_string():
    """Empty raw_input → intake short-circuits → status='error'."""
    llm = MockLLMProvider(default_scenario="pass")
    tel = CapturingTelemetry()
    graph = build_graph(_cfg(), llm, tel)
    result = graph.invoke({"raw_input": ""})
    pkg: BlogPackage = result["final_output"]   # Repair: was final_package

    assert pkg.status == "error"
    assert pkg.notes is not None               # Repair: was error_message
    lower_notes = pkg.notes.lower()
    assert "blank" in lower_notes or "missing" in lower_notes
    # No LLM calls made, so no stage costs
    assert len(pkg.cost.stage_costs) == 0


def test_invalid_raw_input_whitespace_only():
    llm = MockLLMProvider(default_scenario="pass")
    tel = CapturingTelemetry()
    graph = build_graph(_cfg(), llm, tel)
    result = graph.invoke({"raw_input": "   \n\t  "})
    pkg: BlogPackage = result["final_output"]   # Repair: was final_package

    assert pkg.status == "error"


# ---------------------------------------------------------------------------
# Test 8: BlogPackage schema validity — every path returns a valid BlogPackage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario,expected_status", [
    ("pass", "pass"),
    ("needs_human", "needs_human"),
    ("thin_input", "needs_human"),
])
def test_all_paths_return_valid_blog_package(scenario, expected_status):
    """Every terminal path returns a fully validated BlogPackage."""
    llm = MockLLMProvider(default_scenario=scenario)
    pkg = _run(llm)

    assert isinstance(pkg, BlogPackage)
    assert pkg.status == expected_status
    assert pkg.cost is not None              # Repair: was cost_usage
    assert isinstance(pkg.hard_fail_flags, tuple)
    assert isinstance(pkg.source_notes, tuple)


# ---------------------------------------------------------------------------
# Test 9: cost usage is always populated
# ---------------------------------------------------------------------------

def test_cost_usage_always_present():
    """CostUsage is populated on every path including error."""
    for scenario in ("pass", "needs_human", "thin_input"):
        llm = MockLLMProvider(default_scenario=scenario)
        pkg = _run(llm)
        assert pkg.cost is not None              # Repair: was cost_usage
        assert pkg.cost.total_inr >= 0.0
        assert isinstance(pkg.cost.stage_costs, tuple)


def test_cost_usage_total_matches_stage_sum():
    """CostUsage.total_inr must equal sum of all StageCost.cost_inr."""
    llm = MockLLMProvider(default_scenario="pass")
    pkg = _run(llm)
    expected = sum(sc.cost_inr for sc in pkg.cost.stage_costs)
    assert abs(pkg.cost.total_inr - expected) < 1e-9


# ---------------------------------------------------------------------------
# Test 10: no cloud SDK imported in agent/ module tree
# ---------------------------------------------------------------------------

def test_agent_modules_have_no_cloud_sdk_import():
    """Importing Agent 01 in isolation must not pull in any cloud SDK.

    The full suite legitimately imports provider SDKs in core-provider tests, so
    inspecting this pytest process would produce order-dependent false positives.
    """
    probe = """
import sys
banned = ("google.cloud", "vertexai", "boto3", "botocore", "azure")
before = set(sys.modules)
import agent.graph
found = sorted(
    name for name in set(sys.modules) - before
    if name.startswith(banned)
)
if found:
    raise SystemExit("cloud SDKs imported through agent: " + ", ".join(found))
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


# ---------------------------------------------------------------------------
# Test 11: writing_prefs explicit rejection — final repair Issue 3
# ---------------------------------------------------------------------------

def test_writing_prefs_rejected_with_error_status():
    """Non-empty writing_prefs returns status='error' (v1 not supported).

    Final repair Issue 3: writing_prefs was previously silently ignored (telemetry
    only).  The fix explicitly rejects it so callers are not misled into thinking
    their preferences were applied.  Zero provider calls must be made.
    """
    llm = CountingProvider()
    tel = CapturingTelemetry()
    graph = build_graph(_cfg(), llm, tel)
    result = graph.invoke({
        "raw_input": "Machine learning is revolutionising healthcare.",
        "writing_prefs": {"tone": "casual", "audience": "engineers"},
    })
    pkg: BlogPackage = result["final_output"]

    assert pkg.status == "error", (
        f"Expected status='error' when writing_prefs is non-empty (not supported in v1), "
        f"got {pkg.status!r}"
    )
    assert llm.call_count == 0, (
        f"No LLM calls should be made when writing_prefs causes intake rejection; "
        f"got {llm.call_count} calls"
    )
    # The error message should mention writing_prefs
    notes_lower = (pkg.notes or "").lower()
    assert "writing_prefs" in notes_lower, (
        f"notes should mention writing_prefs; got: {pkg.notes!r}"
    )
    # No spend incurred
    assert pkg.cost.total_inr == 0.0, (
        f"Expected zero cost when rejected at intake; got {pkg.cost.total_inr}"
    )


def test_writing_prefs_none_or_empty_does_not_reject():
    """None or empty writing_prefs is treated as absent and does not block the pipeline."""
    llm = MockLLMProvider(default_scenario="pass")

    for writing_prefs_value in (None, {}, ""):
        tel = CapturingTelemetry()
        graph = build_graph(_cfg(), llm, tel)
        result = graph.invoke({
            "raw_input": "Machine learning is revolutionising healthcare.",
            "writing_prefs": writing_prefs_value,
        })
        pkg: BlogPackage = result["final_output"]
        assert pkg.status == "pass", (
            f"writing_prefs={writing_prefs_value!r} should not block the pipeline; "
            f"got {pkg.status!r}"
        )


# ---------------------------------------------------------------------------
# Test 12: unsupported input_type — zero provider calls (recommended test)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("input_type", ["voice", "video", "unknown_format"])
def test_unsupported_input_type_zero_provider_calls(input_type):
    """voice, video, and unknown input types return error with zero LLM calls.

    Final repair recommendation: these paths were untested.  The intake guard
    rejects them before any node makes a provider call.
    """
    llm = CountingProvider()
    tel = CapturingTelemetry()
    graph = build_graph(_cfg(), llm, tel)
    result = graph.invoke({
        "raw_input": "Machine learning is revolutionising healthcare.",
        "input_type": input_type,
    })
    pkg: BlogPackage = result["final_output"]

    assert pkg.status == "error", (
        f"Expected status='error' for input_type={input_type!r}, got {pkg.status!r}"
    )
    assert llm.call_count == 0, (
        f"Expected 0 LLM calls for unsupported input_type={input_type!r}; "
        f"got {llm.call_count}"
    )
    assert pkg.cost.total_inr == 0.0, (
        f"Expected zero cost for rejected input_type; got {pkg.cost.total_inr}"
    )


# ---------------------------------------------------------------------------
# Test 13: span-exit cost preservation — final repair Issue 4
# ---------------------------------------------------------------------------

class SpanExitRaisingTelemetry(CapturingTelemetry):
    """Telemetry whose span context manager raises on __exit__ for a target node.

    Used to simulate a telemetry span-exit failure AFTER the LLM call (i.e., after
    stage_cost was created).  Verifies that the cost is not silently discarded when
    span.__exit__ raises.
    """
    def __init__(self, raise_on_node: str):
        super().__init__()
        self._raise_on_node = raise_on_node

    def span(self, name: str, **attrs):
        base = super().span(name, **attrs)
        if name == self._raise_on_node:
            return _RaisingExitContext(base, self._raise_on_node)
        return base


class _RaisingExitContext:
    """Context manager that delegates enter normally but raises on exit."""
    def __init__(self, inner, node_name: str, *, always: bool = False):
        self._inner = inner
        self._node_name = node_name
        self._always = always

    def __enter__(self):
        return self._inner.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._inner.__exit__(exc_type, exc_val, exc_tb)
        if exc_type is None or self._always:
            raise RuntimeError(
                f"intentional span.__exit__ failure for node={self._node_name!r}"
            )
        return False  # do not suppress existing exceptions


class AlwaysSpanExitRaisingTelemetry(CapturingTelemetry):
    """Raises during span exit even while a provider exception is unwinding."""

    def __init__(self, raise_on_node: str):
        super().__init__()
        self._raise_on_node = raise_on_node

    def span(self, name: str, **attrs):
        base = super().span(name, **attrs)
        if name == self._raise_on_node:
            return _RaisingExitContext(base, self._raise_on_node, always=True)
        return base


class BillableFailureProvider(LLMProvider):
    name = "billable-failure"

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        raise BillableProviderError(
            Usage(
                prompt_tokens=10,
                completion_tokens=5,
                cost_native=0.1,
                currency="USD",
                synthetic=False,
            ),
            "provider_call_failed",
        )


def test_span_exit_failure_preserves_cost_in_ledger():
    """When span.__exit__ raises after a successful LLM call, cost is preserved.

    Final repair Issue 4: the outer try/except in each LLM node catches span-exit
    failures after stage_cost was created and wraps them as BillableNodeError.
    The guard then preserves stage_cost in the ledger.

    Setup: SpanExitRaisingTelemetry raises on span.__exit__ for 'review'.
    The LLM call itself succeeds (stage_cost is created); then span.__exit__ raises.
    Expected: status='error', review cost in ledger, total_inr > 0.
    """
    from core.providers.mock.llm import MockLLMProvider as _Mock
    llm = HighCostMockProvider(cost_per_call_inr=5.0)
    tel = SpanExitRaisingTelemetry(raise_on_node="review")

    graph = build_graph(_cfg(), llm, tel)
    result = graph.invoke({"raw_input": "Machine learning is revolutionising healthcare."})
    pkg: BlogPackage = result["final_output"]

    assert pkg.status == "error", (
        f"Expected status='error' when span.__exit__ raises after successful LLM call, "
        f"got {pkg.status!r}"
    )
    stage_names = {sc.stage for sc in pkg.cost.stage_costs}
    assert "review" in stage_names, (
        "review stage cost must be preserved in the ledger when span.__exit__ raises — "
        "the LLM was billed and that cost must appear in BlogPackage.cost"
    )
    assert pkg.cost.total_inr > 0, (
        f"Expected non-zero total_inr (span-exit failure after LLM call); "
        f"got {pkg.cost.total_inr:.4f}"
    )


def test_billable_provider_failure_plus_span_exit_failure_preserves_cost():
    """A second telemetry failure cannot erase cost reported by BillableProviderError."""
    graph = build_graph(
        _cfg(),
        BillableFailureProvider(),
        AlwaysSpanExitRaisingTelemetry(raise_on_node="normalize"),
    )
    pkg: BlogPackage = graph.invoke(
        {"raw_input": "Machine learning is revolutionising healthcare."}
    )["final_output"]

    assert pkg.status == "error"
    assert pkg.cost.total_inr > 0
    assert {stage.stage for stage in pkg.cost.stage_costs} == {"normalize"}
