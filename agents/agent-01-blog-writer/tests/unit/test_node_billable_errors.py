"""
Test that BillableProviderError from LLM nodes is converted to BillableNodeError
and the cost is preserved in the ledger.

All 5 LLM nodes are tested: normalize, extract_ideas, plan, draft, review.
When LLMProvider.respond() raises BillableProviderError, the node must:
  1. Convert it to BillableNodeError (agent-01-specific exception)
  2. Preserve the incurred cost in stage_cost.cost_inr > 0
  3. Record the correct stage name

The graph's _node_with_error_guard then accumulates this into cost_usage and
sets error_state, so the final status='error' with total_inr > 0.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from typing import Any

from core.interfaces.errors import BillableProviderError
from core.interfaces.llm import LLMProvider, LLMResponse
from core.interfaces.usage import Usage
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import BillableNodeError, StageCost


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_billable_error(cost_native_usd: float = 5.0 / 83.0) -> BillableProviderError:
    """Build a BillableProviderError with synthetic conservative usage."""
    usage = Usage(
        prompt_tokens=512,
        completion_tokens=2048,
        cost_native=cost_native_usd,
        currency="USD",
        synthetic=True,
    )
    return BillableProviderError(usage, "json_parse_failed")


def _cfg(ceiling_inr: float = 50.0) -> dict:
    """Minimal config that passes all node validation (is_mock=True)."""
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
            "input_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
            "max_prompt_tokens": {"cheap": 16384, "strong": 32768},
            "fixed_cost_inr": {"cheap": 0.0, "strong": 0.0},
        },
        "graph": {"max_revision_cycles": 2},
        "service": "test",
        "llm": {
            "provider": "mock",
        },
        "provider": "mock",
    }


class _BillableErrorProvider(LLMProvider):
    """LLMProvider that always raises BillableProviderError."""
    name = "billable_error_mock"

    def __init__(self, error: BillableProviderError) -> None:
        self._error = error

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None) -> LLMResponse:
        raise self._error


class _FencedDraftProvider(LLMProvider):
    """LLMProvider that returns a draft wrapped in a Markdown code fence."""
    name = "fenced_draft_mock"

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None) -> LLMResponse:
        usage = Usage(
            prompt_tokens=50,
            completion_tokens=50,
            cost_native=0.001,
            currency="USD",
            synthetic=False,
        )
        return LLMResponse(
            text="```markdown\n# Clean Blog Title\n\nThis is the actual blog body.\n```",
            usage=usage,
        )


def _make_tel() -> StdoutTelemetry:
    tel = StdoutTelemetry(service="test")
    return tel


# Minimal state shapes for each node
def _normalize_state() -> dict:
    return {"raw_input": "some input", "cost_usage": []}


def _extract_ideas_state() -> dict:
    return {"normalized_content": "some content", "cost_usage": []}


def _plan_state() -> dict:
    from core.providers.mock.llm import MockLLMProvider, _mock_data, _apply_scenario
    from agent.schemas import ExtractedIdeas
    data = _mock_data(ExtractedIdeas)
    data = _apply_scenario(data, "pass", schema=ExtractedIdeas)
    extracted = ExtractedIdeas.model_validate(data)
    return {
        "normalized_content": "some content",
        "extracted_ideas": extracted,
        "cost_usage": [],
    }


def _draft_state() -> dict:
    from core.providers.mock.llm import MockLLMProvider, _mock_data, _apply_scenario
    from agent.schemas import BlogPlan
    data = _mock_data(BlogPlan)
    data = _apply_scenario(data, "pass", schema=BlogPlan)
    plan = BlogPlan.model_validate(data)
    return {
        "normalized_content": "some content",
        "blog_plan": plan,
        "quality": None,
        "revision_count": 0,
        "cost_usage": [],
    }


def _review_state() -> dict:
    from core.providers.mock.llm import MockLLMProvider, _mock_data, _apply_scenario
    from agent.schemas import BlogPlan
    data = _mock_data(BlogPlan)
    data = _apply_scenario(data, "pass", schema=BlogPlan)
    plan = BlogPlan.model_validate(data)
    return {
        "draft": "Some draft text",
        "blog_plan": plan,
        "raw_input": "original input",
        "extracted_ideas": None,
        "cost_usage": [],
    }


# ---------------------------------------------------------------------------
# Test each node individually
# ---------------------------------------------------------------------------

class TestNormalizeBillableError:
    def test_billable_provider_error_becomes_billable_node_error(self):
        """normalize: BillableProviderError → BillableNodeError with cost > 0."""
        from agent.nodes.normalize import make_normalize_node

        bpe = _make_billable_error(cost_native_usd=5.0 / 83.0)
        llm = _BillableErrorProvider(bpe)
        tel = _make_tel()
        cfg = _cfg()

        node_fn = make_normalize_node(cfg, llm, tel)
        state = _normalize_state()

        with pytest.raises(BillableNodeError) as exc_info:
            node_fn(state)

        err = exc_info.value
        assert err.stage_cost.cost_inr > 0, "cost must be > 0 in ledger entry"
        assert err.stage_cost.stage == "normalize"
        # Node wraps BillableProviderError.category in a RuntimeError stub (content-free)
        assert isinstance(err.cause, RuntimeError)
        assert "billable-provider-failure:" in str(err.cause)
        assert "json_parse_failed" in str(err.cause)

    def test_billable_node_error_cost_is_approximate(self):
        """Cost in BillableNodeError is derived from the conservative usage, not zero."""
        from agent.nodes.normalize import make_normalize_node

        # synthetic=True usage with known cost
        usage = Usage(
            prompt_tokens=256, completion_tokens=2048,
            cost_native=10.0 / 83.0, currency="USD", synthetic=True,
        )
        bpe = BillableProviderError(usage, "usage_extraction_failed")
        llm = _BillableErrorProvider(bpe)
        tel = _make_tel()

        node_fn = make_normalize_node(_cfg(), llm, tel)
        with pytest.raises(BillableNodeError) as exc_info:
            node_fn(_normalize_state())

        # cost_inr = cost_native * fx_rate = (10/83) * 83 = 10
        assert exc_info.value.stage_cost.cost_inr > 0


class TestExtractIdeasBillableError:
    def test_billable_provider_error_becomes_billable_node_error(self):
        """extract_ideas: BillableProviderError → BillableNodeError with cost > 0."""
        from agent.nodes.extract_ideas import make_extract_ideas_node

        bpe = _make_billable_error()
        llm = _BillableErrorProvider(bpe)
        tel = _make_tel()

        node_fn = make_extract_ideas_node(_cfg(), llm, tel)
        with pytest.raises(BillableNodeError) as exc_info:
            node_fn(_extract_ideas_state())

        err = exc_info.value
        assert err.stage_cost.cost_inr > 0
        assert err.stage_cost.stage == "extract_ideas"


class TestPlanBillableError:
    def test_billable_provider_error_becomes_billable_node_error(self):
        """plan: BillableProviderError → BillableNodeError with cost > 0."""
        from agent.nodes.plan import make_plan_node

        bpe = _make_billable_error()
        llm = _BillableErrorProvider(bpe)
        tel = _make_tel()

        node_fn = make_plan_node(_cfg(), llm, tel)
        with pytest.raises(BillableNodeError) as exc_info:
            node_fn(_plan_state())

        err = exc_info.value
        assert err.stage_cost.cost_inr > 0
        assert err.stage_cost.stage == "plan"


class TestDraftBillableError:
    def test_billable_provider_error_becomes_billable_node_error(self):
        """draft: BillableProviderError → BillableNodeError with cost > 0."""
        from agent.nodes.draft import make_draft_node

        bpe = _make_billable_error()
        llm = _BillableErrorProvider(bpe)
        tel = _make_tel()

        node_fn = make_draft_node(_cfg(), llm, tel)
        with pytest.raises(BillableNodeError) as exc_info:
            node_fn(_draft_state())

        err = exc_info.value
        assert err.stage_cost.cost_inr > 0
        assert err.stage_cost.stage == "draft"


class TestDraftOutputCleanup:
    def test_draft_strips_outer_markdown_code_fence(self):
        """draft: provider may return fenced Markdown, but state stores raw blog Markdown."""
        from agent.nodes.draft import make_draft_node

        llm = _FencedDraftProvider()
        tel = _make_tel()

        node_fn = make_draft_node(_cfg(), llm, tel)
        result = node_fn(_draft_state())

        assert result["draft"].startswith("# Clean Blog Title")
        assert "This is the actual blog body." in result["draft"]
        assert "```" not in result["draft"]


class TestReviewBillableError:
    def test_billable_provider_error_becomes_billable_node_error(self):
        """review: BillableProviderError → BillableNodeError with cost > 0."""
        from agent.nodes.review import make_review_node

        bpe = _make_billable_error()
        llm = _BillableErrorProvider(bpe)
        tel = _make_tel()

        node_fn = make_review_node(_cfg(), llm, tel)
        with pytest.raises(BillableNodeError) as exc_info:
            node_fn(_review_state())

        err = exc_info.value
        assert err.stage_cost.cost_inr > 0
        assert err.stage_cost.stage == "review"


# ---------------------------------------------------------------------------
# Integration: graph error handler accumulates cost from BillableNodeError
# ---------------------------------------------------------------------------

class TestGraphAccumulatesCostFromBillableError:
    """
    When BillableProviderError occurs in normalize, the graph's _node_with_error_guard
    accumulates the stage cost and returns status='error' with total_inr > 0.
    """

    def test_billable_provider_error_in_normalize_yields_error_status_with_cost(self):
        """BillableProviderError during normalize → status=error, total_inr > 0."""
        from agent.graph import build_graph
        from agent.schemas import BlogPackage

        usage = Usage(
            prompt_tokens=256, completion_tokens=2048,
            cost_native=5.0 / 83.0, currency="USD", synthetic=True,
        )
        bpe = BillableProviderError(usage, "json_parse_failed")
        llm = _BillableErrorProvider(bpe)

        from core.providers.mock.telemetry import StdoutTelemetry
        tel = StdoutTelemetry(service="test")
        cfg = _cfg()

        graph = build_graph(cfg, llm, tel)
        result = graph.invoke({"raw_input": "Some blog topic."})
        pkg: BlogPackage = result["final_output"]

        assert pkg.status == "error", f"Expected 'error', got {pkg.status!r}"
        assert pkg.cost.total_inr > 0, (
            f"total_inr={pkg.cost.total_inr} — cost must be > 0 when a real call was billed"
        )
        stage_names = {sc.stage for sc in pkg.cost.stage_costs}
        assert "normalize" in stage_names, (
            f"normalize stage cost must appear in ledger; got stages={stage_names}"
        )


# ---------------------------------------------------------------------------
# Issue 1 — Every LLM node must pass _authorized_prompt_tokens in params
# ---------------------------------------------------------------------------

class _CapturingProvider(LLMProvider):
    """LLMProvider that captures params from respond() and returns a mock response."""
    name = "capturing_mock"

    def __init__(self) -> None:
        self.captured_params: dict = {}

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None) -> LLMResponse:
        self.captured_params = dict(params or {})
        # Return a valid mock response
        from core.providers.mock.llm import MockLLMProvider, _mock_data, _apply_scenario
        usage = Usage(prompt_tokens=50, completion_tokens=25,
                      cost_native=0.001, currency="USD", synthetic=False)
        if response_schema is not None:
            data = _mock_data(response_schema)
            data = _apply_scenario(data, "pass", schema=response_schema)
            validated = response_schema.model_validate(data)
            return LLMResponse(structured=validated, usage=usage)
        return LLMResponse(text="mock response text", usage=usage)


class TestNodesPassAuthorizedPromptTokens:
    """Every LLM node must include _authorized_prompt_tokens in params to llm.respond()."""

    def _make_provider(self):
        return _CapturingProvider()

    def test_normalize_passes_authorized_prompt_tokens(self):
        from agent.nodes.normalize import make_normalize_node
        provider = self._make_provider()
        tel = _make_tel()
        node_fn = make_normalize_node(_cfg(), provider, tel)
        node_fn(_normalize_state())
        assert "_authorized_prompt_tokens" in provider.captured_params, (
            "normalize did not pass _authorized_prompt_tokens"
        )
        v = provider.captured_params["_authorized_prompt_tokens"]
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0

    def test_extract_ideas_passes_authorized_prompt_tokens(self):
        from agent.nodes.extract_ideas import make_extract_ideas_node
        provider = self._make_provider()
        tel = _make_tel()
        node_fn = make_extract_ideas_node(_cfg(), provider, tel)
        node_fn(_extract_ideas_state())
        assert "_authorized_prompt_tokens" in provider.captured_params, (
            "extract_ideas did not pass _authorized_prompt_tokens"
        )
        v = provider.captured_params["_authorized_prompt_tokens"]
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0

    def test_plan_passes_authorized_prompt_tokens(self):
        from agent.nodes.plan import make_plan_node
        provider = self._make_provider()
        tel = _make_tel()
        node_fn = make_plan_node(_cfg(), provider, tel)
        node_fn(_plan_state())
        assert "_authorized_prompt_tokens" in provider.captured_params, (
            "plan did not pass _authorized_prompt_tokens"
        )
        v = provider.captured_params["_authorized_prompt_tokens"]
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0

    def test_draft_passes_authorized_prompt_tokens(self):
        from agent.nodes.draft import make_draft_node
        provider = self._make_provider()
        tel = _make_tel()
        node_fn = make_draft_node(_cfg(), provider, tel)
        node_fn(_draft_state())
        assert "_authorized_prompt_tokens" in provider.captured_params, (
            "draft did not pass _authorized_prompt_tokens"
        )
        v = provider.captured_params["_authorized_prompt_tokens"]
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0

    def test_review_passes_authorized_prompt_tokens(self):
        from agent.nodes.review import make_review_node
        provider = self._make_provider()
        tel = _make_tel()
        node_fn = make_review_node(_cfg(), provider, tel)
        node_fn(_review_state())
        assert "_authorized_prompt_tokens" in provider.captured_params, (
            "review did not pass _authorized_prompt_tokens"
        )
        v = provider.captured_params["_authorized_prompt_tokens"]
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0
