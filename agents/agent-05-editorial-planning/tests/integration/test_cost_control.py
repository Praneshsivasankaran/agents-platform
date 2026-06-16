"""Cost-control regression tests for Agent 05 (offline, no real GCP).

These tests exercise the LIVE provider path (``is_mock=False`` + real per-token pricing from the
GCP overlay) using injected provider doubles instead of Vertex, so the budget preflight, strict
output caps, top-N briefs, graceful budget-limited degradation, and the ``generation_used_llm``
flag are all verified without spending money.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.interfaces import LLMResponse
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import (
    EditorialPlanningPackage,
    PlatformPlan,
    PlatformStrategyPackage,
)
from agent.workflow import build_graph


_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def live_cfg(**cost_overrides: Any) -> dict[str, Any]:
    """GCP-equivalent live config (is_mock=False, real pricing, strict caps), merged offline."""
    base = yaml.safe_load((_CONFIG_DIR / "base.yaml").read_text(encoding="utf-8"))
    gcp = yaml.safe_load((_CONFIG_DIR / "gcp.yaml").read_text(encoding="utf-8"))
    cfg = _deep_merge(base, gcp)
    cfg["cost"].update(cost_overrides)
    return cfg


def big_request(count_per_week: int = 7, **overrides: Any) -> dict[str, Any]:
    """A full-month, high-frequency campaign (many planned items)."""
    data: dict[str, Any] = {
        "brand_name": "Northstar Wellness",
        "business_goal": "Drive qualified leads for a corporate wellness program",
        "target_audience": "HR leaders at mid-market companies",
        "campaign_theme": "Burnout prevention for distributed teams",
        "platforms": ["blog", "linkedin", "email"],
        "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
        "posting_frequency": {"cadence": "weekly", "count_per_week": count_per_week},
        "brand_voice": "warm, expert, practical",
        "content_pillars": ["education", "proof", "conversion"],
        "existing_ideas": ["Checklist for spotting team burnout"],
        "constraints": ["Avoid medical diagnosis claims"],
    }
    data.update(overrides)
    return data


class PricedMockLLM(MockLLMProvider):
    """Simulates a real Vertex call: returns mock structure but bills realistically.

    Cost is computed from the SAME per-token config prices and the ``max_tokens`` the workflow
    sent — i.e. the provider consumes its full allowed output budget (worst case). It records the
    response schema of every call so tests can see which stages actually ran.
    """

    def __init__(self, cfg: dict) -> None:
        super().__init__(default_scenario="pass")
        cost = cfg["cost"]
        self._out = cost["output_cost_per_token_inr"]
        self._in = cost["input_cost_per_token_inr"]
        self._fx = float(cost["fx_rates"]["USD"])
        self.calls: list[str] = []

    def _usage(self, tier: str, params: dict | None) -> Usage:
        params = params or {}
        max_tokens = int(params.get("max_tokens") or 2048)
        prompt_tokens = int(params.get("_authorized_prompt_tokens") or 200)
        cost_inr = prompt_tokens * self._in[tier] + max_tokens * self._out[tier]
        return Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=max_tokens,
            cost_native=cost_inr / self._fx,
            currency="USD",
            synthetic=False,
        )

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        self.calls.append(getattr(response_schema, "__name__", "text"))
        base = super().respond(messages, tier=tier, params=params, tools=tools, response_schema=response_schema)
        usage = self._usage(tier, params)
        if response_schema is not None:
            return LLMResponse(structured=base.structured, usage=usage)
        return LLMResponse(text=base.text or "ok", usage=usage)


class UsableStrategyLLM(PricedMockLLM):
    """Like PricedMockLLM but returns a genuinely usable platform strategy (so a stage's LLM
    output is accepted), to prove ``generation_used_llm`` flips true when output is used."""

    def respond(self, messages, *, tier, params=None, tools=None, response_schema=None):
        self.calls.append(getattr(response_schema, "__name__", "text"))
        usage = self._usage(tier, params)
        if response_schema is PlatformStrategyPackage:
            strategy = PlatformStrategyPackage(
                platform_plans=(
                    PlatformPlan(
                        platform="blog",
                        role="Educate HR leaders on burnout prevention with practical long-form articles.",
                        recommended_content_types=("educational article", "how-to guide"),
                        cadence_notes="Weekly long-form planning slot; review only, no scheduling.",
                        cta_guidance="Invite readers to a human-reviewed next step toward the program.",
                    ),
                    PlatformPlan(
                        platform="linkedin",
                        role="Build authority with concise, practical posts for HR decision-makers.",
                        recommended_content_types=("thought leadership post", "carousel outline"),
                        cadence_notes="Several short posts per week, planning only.",
                        cta_guidance="Encourage profile visits and saved posts; no outbound action.",
                    ),
                    PlatformPlan(
                        platform="email",
                        role="Nurture subscribers with curated burnout-prevention guidance.",
                        recommended_content_types=("newsletter feature", "nurture email"),
                        cadence_notes="Weekly newsletter planning slot.",
                        cta_guidance="Invite replies and demo interest under human review.",
                    ),
                ),
                notes=("LLM-generated platform strategy.",),
            )
            return LLMResponse(structured=strategy, usage=usage)
        base = MockLLMProvider.respond(self, messages, tier=tier, params=params, tools=tools, response_schema=response_schema)
        if response_schema is not None:
            return LLMResponse(structured=base.structured, usage=usage)
        return LLMResponse(text=base.text or "ok", usage=usage)


def _run(raw_input: dict[str, Any], cfg: dict[str, Any], llm) -> EditorialPlanningPackage:
    graph = build_graph(cfg, llm, StdoutTelemetry(service="agent05-cost-test"))
    return graph.invoke({"raw_input": raw_input})["final_output"]


def test_preflight_blocks_expensive_stage_before_exceeding_ceiling() -> None:
    # A very low ceiling means most stages cannot be afforded. The pre-call gate must block them
    # (no provider call) and the run must NEVER exceed the ceiling.
    cfg = live_cfg(ceiling_inr=4.0)
    llm = PricedMockLLM(cfg)

    package = _run(big_request(), cfg, llm)

    assert package.cost.total_inr <= 4.0, f"cost Rs{package.cost.total_inr} exceeded ceiling"
    assert package.status == "needs_review_budget_limited"
    assert len(llm.calls) < 4, "expected at least one expensive stage to be blocked pre-call"
    # Still partial-but-useful and schema-valid.
    assert package.editorial_calendar
    assert package.content_briefs


def test_full_month_high_frequency_plan_stays_under_ceiling() -> None:
    cfg = live_cfg()  # ceiling 30
    llm = PricedMockLLM(cfg)

    package = _run(big_request(count_per_week=7), cfg, llm)

    assert package.status != "stopped_cost_ceiling"
    assert package.status != "error"
    assert package.cost.total_inr < 30.0, f"cost Rs{package.cost.total_inr} not under hard ceiling"
    assert package.cost.total_inr < 15.0, f"cost Rs{package.cost.total_inr} above the Rs15 target"
    assert len(llm.calls) == 4, "all four billable stages should run within budget"
    assert package.editorial_calendar
    assert package.content_briefs


def test_generation_used_llm_true_when_llm_output_is_used() -> None:
    cfg = live_cfg()
    llm = UsableStrategyLLM(cfg)

    package = _run(big_request(count_per_week=3), cfg, llm)

    assert package.generation_used_llm is True
    assert package.cost.total_inr < 30.0


def test_budget_limited_output_remains_schema_valid() -> None:
    cfg = live_cfg(ceiling_inr=4.0)
    llm = PricedMockLLM(cfg)

    package = _run(big_request(), cfg, llm)

    assert isinstance(package, EditorialPlanningPackage)
    assert package.status == "needs_review_budget_limited"
    # Round-trips through validation (frozen, strict, deeply-immutable contract).
    revalidated = EditorialPlanningPackage.model_validate(package.model_dump())
    assert revalidated.status == "needs_review_budget_limited"
    assert package.editorial_calendar
    assert package.content_briefs
    assert package.cost.total_inr <= 4.0
