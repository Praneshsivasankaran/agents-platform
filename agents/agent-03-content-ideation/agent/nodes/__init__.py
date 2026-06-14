"""LangGraph node factories for Agent 03."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from core.cost import (
    CostCeilingExceeded,
    authorize_call,
    estimate_prompt_tokens,
    resolve_is_mock,
    total_cost_inr,
    usage_cost_inr,
)
from core.interfaces import BillableProviderError, LLMResponse, Telemetry
from core.interfaces.llm import LLMProvider, Tier

from ..contracts import (
    BillableNodeError,
    ContentIdeationPackage,
    ContentIdeationRequest,
    CostUsage,
    LLMIdeaBundle,
    StageCost,
)
from ..prompts import SYSTEM_PROMPT, idea_generation_prompt, quality_review_prompt
from ..quality import (
    analyze_audience,
    build_blog_brief,
    build_repurposing_brief,
    coerce_llm_ideas,
    deterministic_ideas,
    detect_request_risks,
    determine_recommended_next_agent,
    generate_content_themes,
    generate_ctas,
    generate_hooks,
    normalize_campaign_context,
    recommended_formats,
    run_quality_gate,
    validate_campaign_brief,
)
from ..state import Agent03State


_ALIASES = {
    "keywords": "optional_keywords",
    "existing_notes": "optional_notes",
    "notes": "optional_notes",
    "constraints": "optional_constraints",
    "things_to_avoid": "optional_constraints",
    "preferred_formats": "optional_content_type_preference",
    "content_type_preference": "optional_content_type_preference",
}


def _request_from_state(state: Agent03State) -> ContentIdeationRequest:
    existing = state.get("request")
    if isinstance(existing, ContentIdeationRequest):
        return existing
    raw = state.get("raw_input")
    if isinstance(raw, ContentIdeationRequest):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("Agent 03 input must be a serialized campaign brief object")
    data = dict(raw)
    for old_key, new_key in _ALIASES.items():
        if old_key in data and new_key not in data:
            data[new_key] = data[old_key]
    return ContentIdeationRequest.model_validate(data)


def _safe_validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        fields = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "input"
            fields.append(loc)
        return "Missing or invalid campaign brief fields: " + ", ".join(dict.fromkeys(fields))
    return "Invalid Agent 03 input: " + type(exc).__name__


def _stage_tier(cfg: dict, stage_name: str, default: Tier) -> Tier:
    tier = cfg.get("llm", {}).get("stage_tiers", {}).get(stage_name, default)
    if tier in ("cheap", "strong"):
        return tier
    raise ValueError(f"llm.stage_tiers[{stage_name!r}] must be 'cheap' or 'strong'")


def _stage_pricing(cfg: dict, tier: Tier) -> tuple[float, float, float, int, int]:
    cost_cfg = cfg.get("cost", {})
    output_cpt = float(cost_cfg.get("output_cost_per_token_inr", {}).get(tier, 0.0))
    input_cpt = float(cost_cfg.get("input_cost_per_token_inr", {}).get(tier, 0.0))
    fixed = float(cost_cfg.get("fixed_cost_inr", {}).get(tier, 0.0))
    max_prompt = int(cost_cfg.get("max_prompt_tokens", {}).get(tier, 32768))
    max_output = int(cost_cfg.get("max_output_tokens", {}).get(tier, 0))
    return output_cpt, input_cpt, fixed, max_prompt, max_output


def _billable_llm_call(
    *,
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    state: Agent03State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[LLMResponse, StageCost]:
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr = float(cost_cfg.get("ceiling_inr", 20.0))
    estimated_costs = {k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()}
    is_mock = resolve_is_mock(cfg)
    output_cpt, input_cpt, fixed, max_prompt, tier_max_output = _stage_pricing(cfg, tier)
    max_output = int(cost_cfg.get("max_output_tokens", {}).get(stage_name, tier_max_output))

    prompt_tokens_est = estimate_prompt_tokens(messages, response_schema)
    if prompt_tokens_est > max_prompt:
        raise CostCeilingExceeded(
            f"{stage_name}: prompt estimate {prompt_tokens_est} exceeds max_prompt_tokens={max_prompt}"
        )
    auth = authorize_call(
        stage_name=stage_name,
        stage_costs=state.get("cost_usage", []),
        ceiling_inr=ceiling_inr,
        estimated_costs=estimated_costs,
        downstream_stages=downstream_stages,
        output_cost_per_token_inr=output_cpt,
        input_cost_per_token_inr=input_cpt,
        prompt_tokens_estimate=prompt_tokens_est,
        fixed_cost_inr=fixed,
        is_mock=is_mock,
    )
    params: dict[str, Any] = {"_authorized_prompt_tokens": prompt_tokens_est}
    if auth.max_tokens is not None:
        params["max_tokens"] = min(auth.max_tokens, max_output) if max_output > 0 else auth.max_tokens

    try:
        with tel.span(stage_name) as span_id:
            try:
                response = llm.respond(
                    messages,
                    tier=tier,
                    params=params,
                    response_schema=response_schema,
                )
            except BillableProviderError as bpe:
                stage_cost = StageCost(
                    stage=stage_name,
                    cost_inr=usage_cost_inr(bpe.usage, fx_rates=fx_rates),
                    tier=tier,
                    tokens_prompt=bpe.usage.prompt_tokens,
                    tokens_completion=bpe.usage.completion_tokens,
                )
                raise BillableNodeError(
                    stage_cost,
                    RuntimeError(f"billable-provider-failure:{bpe.category}"),
                ) from None
            stage_cost = StageCost(
                stage=stage_name,
                cost_inr=usage_cost_inr(response.usage, fx_rates=fx_rates),
                tier=tier,
                tokens_prompt=response.usage.prompt_tokens,
                tokens_completion=response.usage.completion_tokens,
            )
            try:
                tel.record_usage(response.usage, node=stage_name, tier=tier, span_id=span_id)
                tel.metric("stage.cost_inr", stage_cost.cost_inr, node=stage_name)
                tel.log(f"{stage_name}.complete", span_id=span_id)
            except Exception as exc:
                raise BillableNodeError(stage_cost, exc) from exc
            return response, stage_cost
    except BillableNodeError:
        raise
    except Exception as exc:
        if "stage_cost" in locals():
            raise BillableNodeError(stage_cost, exc) from exc
        raise


def _best_effort_llm_call(
    *,
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    state: Agent03State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[object | None, list[StageCost], bool]:
    try:
        response, stage_cost = _billable_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name=stage_name,
            tier=tier,
            messages=messages,
            downstream_stages=downstream_stages,
            response_schema=response_schema,
        )
        return response.structured, [stage_cost], False
    except CostCeilingExceeded:
        raise
    except BillableNodeError as be:
        _log_provider_hiccup(tel, stage_name, type(be.cause).__name__)
        return None, [be.stage_cost], True
    except Exception as exc:  # noqa: BLE001
        _log_provider_hiccup(tel, stage_name, type(exc).__name__)
        return None, [], True


def _log_provider_hiccup(tel: Telemetry, stage_name: str, kind: str) -> None:
    try:
        tel.log(f"{stage_name}.provider_hiccup", node=stage_name, kind=kind)
    except Exception:
        pass


def make_intake_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def intake(state: Agent03State) -> dict[str, Any]:
        with tel.span("intake_request") as span_id:
            try:
                request = _request_from_state(state)
            except Exception as exc:  # noqa: BLE001
                message = _safe_validation_message(exc)
                tel.log("intake_request.invalid", span_id=span_id)
                return {
                    "request_id": state.get("request_id") or f"agent03-{uuid4().hex[:12]}",
                    "status": "needs_more_input",
                    "notes": message,
                    "validation_errors": (message,),
                    "cost_usage": [],
                    "hard_fails": [],
                    "cost_gate_ok": True,
                    "generation_used_llm": False,
                }
            tel.log("intake_request.accepted", span_id=span_id, ideas=request.number_of_ideas)
            return {
                "request_id": state.get("request_id") or f"agent03-{uuid4().hex[:12]}",
                "request": request,
                "status": "running",
                "cost_usage": [],
                "hard_fails": [],
                "cost_gate_ok": True,
                "generation_used_llm": False,
            }

    return intake


def make_validate_campaign_brief_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def validate_node(state: Agent03State) -> dict[str, Any]:
        request = state["request"]
        valid, reason = validate_campaign_brief(request)
        risks, hard_fails = detect_request_risks(request)
        with tel.span("validate_campaign_brief") as span_id:
            tel.log("validate_campaign_brief.complete", span_id=span_id, valid=valid)
        update: dict[str, Any] = {"request_risk_flags": risks}
        if hard_fails:
            update["hard_fails"] = list(hard_fails)
        if not valid:
            update.update({"status": "needs_more_input", "notes": reason or "Campaign brief is incomplete."})
        return update

    return validate_node


def make_analyze_audience_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def analyze_node(state: Agent03State) -> dict[str, Any]:
        request = state["request"]
        summary = normalize_campaign_context(request)
        audience = analyze_audience(request)
        with tel.span("analyze_audience") as span_id:
            tel.log("analyze_audience.complete", span_id=span_id)
        return {"campaign_summary": summary, "audience_insights": audience}

    return analyze_node


def make_generate_content_themes_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def themes_node(state: Agent03State) -> dict[str, Any]:
        themes = generate_content_themes(
            state["request"],
            state["campaign_summary"],
            state["audience_insights"],
        )
        with tel.span("generate_content_themes") as span_id:
            tel.log("generate_content_themes.complete", span_id=span_id, theme_count=len(themes))
        return {"content_themes": themes}

    return themes_node


def make_generate_content_ideas_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def ideas_node(state: Agent03State) -> dict[str, Any]:
        request = state["request"]
        themes = state["content_themes"]
        themes_text = "\n".join(f"- {theme.name}: {theme.description}" for theme in themes)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": idea_generation_prompt(request, themes_text)},
        ]
        tier = _stage_tier(cfg, "generate_content_ideas", "cheap")
        structured, stage_costs, _hiccup = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="generate_content_ideas",
            tier=tier,
            messages=messages,
            downstream_stages=("quality_scoring",),
            response_schema=LLMIdeaBundle,
        )
        bundle = structured if isinstance(structured, LLMIdeaBundle) else None
        base = deterministic_ideas(
            request,
            state["campaign_summary"],
            state["audience_insights"],
            themes,
        )
        if bundle is not None:
            ideas, used = coerce_llm_ideas(
                request,
                state["campaign_summary"],
                state["audience_insights"],
                themes,
                bundle,
                base,
            )
        else:
            ideas, used = base, 0
        ideas = tuple(sorted(ideas, key=lambda idea: idea.priority_score, reverse=True))
        tel.log("generate_content_ideas.package", idea_count=len(ideas), llm_ideas_used=used)
        return {"content_ideas": ideas, "generation_used_llm": used > 0, "cost_usage": stage_costs}

    return ideas_node


def make_generate_hooks_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def hooks_node(state: Agent03State) -> dict[str, Any]:
        hooks = generate_hooks(state["request"], state["content_ideas"])
        ctas = generate_ctas(state["request"])
        with tel.span("generate_hooks") as span_id:
            tel.log("generate_hooks.complete", span_id=span_id, hook_count=len(hooks))
        return {"hooks": hooks, "cta_suggestions": ctas}

    return hooks_node


def make_create_blog_brief_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def blog_brief_node(state: Agent03State) -> dict[str, Any]:
        risk_flags = tuple(state.get("request_risk_flags", ()))
        brief = build_blog_brief(
            state["request"],
            state["campaign_summary"],
            state["audience_insights"],
            state["content_ideas"],
            state["cta_suggestions"],
            risk_flags,
        )
        with tel.span("create_blog_brief_for_agent_01") as span_id:
            tel.log("create_blog_brief_for_agent_01.complete", span_id=span_id, created=brief is not None)
        return {"blog_brief_for_agent_01": brief}

    return blog_brief_node


def make_create_repurposing_brief_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def repurposing_brief_node(state: Agent03State) -> dict[str, Any]:
        risk_flags = tuple(state.get("request_risk_flags", ()))
        brief = build_repurposing_brief(
            state["request"],
            state["content_themes"],
            state["content_ideas"],
            state["hooks"],
            state["cta_suggestions"],
            risk_flags,
        )
        with tel.span("create_repurposing_brief_for_agent_02") as span_id:
            tel.log(
                "create_repurposing_brief_for_agent_02.complete",
                span_id=span_id,
                created=brief is not None,
            )
        return {"repurposing_brief_for_agent_02": brief}

    return repurposing_brief_node


def make_quality_scoring_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def quality_node(state: Agent03State) -> dict[str, Any]:
        review_payload = {
            "campaign_summary": state.get("campaign_summary").model_dump(mode="json")
            if state.get("campaign_summary")
            else None,
            "idea_count": len(state.get("content_ideas", ())),
            "top_idea": state.get("content_ideas", ())[0].model_dump(mode="json")
            if state.get("content_ideas")
            else None,
            "risk_flags": list(state.get("request_risk_flags", ())),
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": quality_review_prompt(json.dumps(review_payload, sort_keys=True))},
        ]
        tier = _stage_tier(cfg, "quality_scoring", "cheap")
        _structured, stage_costs, _hiccup = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="quality_scoring",
            tier=tier,
            messages=messages,
        )
        quality = run_quality_gate(
            request=state.get("request"),
            summary=state.get("campaign_summary"),
            audience=state.get("audience_insights"),
            themes=state.get("content_themes", ()),
            ideas=state.get("content_ideas", ()),
            hooks=state.get("hooks", ()),
            ctas=state.get("cta_suggestions", ()),
            blog_brief=state.get("blog_brief_for_agent_01"),
            repurposing_brief=state.get("repurposing_brief_for_agent_02"),
            request_hard_fails=tuple(state.get("hard_fails", [])),
            request_risk_flags=tuple(state.get("request_risk_flags", ())),
        )
        recommended = determine_recommended_next_agent(
            state["request"],
            state.get("content_ideas", ()),
            quality,
        )
        with tel.span("quality_scoring") as span_id:
            tel.metric("quality.overall_score", quality.overall_score, node="quality_scoring")
            tel.log("quality_scoring.complete", span_id=span_id, score=quality.overall_score)
        update: dict[str, Any] = {
            "quality_report": quality,
            "recommended_next_agent": recommended,
            "cost_usage": stage_costs,
        }
        if quality.hard_fails:
            update["hard_fails"] = list(quality.hard_fails)
        return update

    return quality_node


def make_assemble_package_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 20.0))

    def assemble_node(state: Agent03State) -> dict[str, Any]:
        stage_costs = list(state.get("cost_usage", []))
        total = round(total_cost_inr(stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
        status = _determine_status(state, total=total, ceiling_inr=ceiling_inr)
        quality = state.get("quality_report")
        notes = _determine_notes(state, status)
        package = ContentIdeationPackage(
            status=status,  # type: ignore[arg-type]
            package_id=state.get("request_id", ""),
            campaign_summary=state.get("campaign_summary"),
            audience_insights=state.get("audience_insights"),
            content_themes=state.get("content_themes", ()),
            content_ideas=state.get("content_ideas", ()),
            hooks=state.get("hooks", ()),
            cta_suggestions=state.get("cta_suggestions", ()),
            recommended_formats=recommended_formats(state.get("content_ideas", ())),
            quality_score=quality.overall_score if quality else 0,
            quality_notes=quality.improvement_notes if quality else (),
            risk_flags=quality.risk_flags if quality else tuple(state.get("request_risk_flags", ())),
            blog_brief_for_agent_01=state.get("blog_brief_for_agent_01"),
            repurposing_brief_for_agent_02=state.get("repurposing_brief_for_agent_02"),
            recommended_next_agent=state.get("recommended_next_agent", "Human Review"),  # type: ignore[arg-type]
            quality_report=quality,
            cost=cost,
            notes=notes,
            generation_used_llm=bool(state.get("generation_used_llm", False)),
        )
        with tel.span("assemble_content_ideation_package") as span_id:
            tel.metric("total.cost_inr", total, node="assemble_content_ideation_package")
            tel.log("assemble_content_ideation_package.complete", span_id=span_id, status=status)
        return {"status": status, "final_output": package}

    return assemble_node


def _determine_status(state: Agent03State, *, total: float, ceiling_inr: float) -> str:
    if not state.get("cost_gate_ok", True) or total > ceiling_inr:
        return "stopped_cost_ceiling"
    if state.get("error_state") is not None:
        return "error"
    if state.get("status") == "needs_more_input":
        return "needs_more_input"
    quality = state.get("quality_report")
    if quality is not None and quality.passed:
        return "pass"
    return "needs_human"


def _determine_notes(state: Agent03State, status: str) -> str:
    if status == "stopped_cost_ceiling":
        return "Cost ceiling reached; run stopped before generating more ideation output."
    if status == "error":
        error = state.get("error_state", {})
        return f"Error in {error.get('node', 'unknown')} ({error.get('kind', 'Error')})"
    if status == "needs_more_input":
        return state.get("notes", "Campaign brief needs more required context.")
    if status == "pass":
        return "Review-ready Content Ideation Package generated. No external action was taken."
    quality = state.get("quality_report")
    if quality and quality.hard_fails:
        terminal = [fail.reason for fail in quality.hard_fails if fail.severity == "terminal"]
        if terminal:
            return "Terminal quality issue: " + "; ".join(terminal)
        return "Quality gate did not pass; improve the brief or revise the generated ideas."
    return "Human review required before using this ideation package downstream."


__all__ = [
    "make_analyze_audience_node",
    "make_assemble_package_node",
    "make_create_blog_brief_node",
    "make_create_repurposing_brief_node",
    "make_generate_content_ideas_node",
    "make_generate_content_themes_node",
    "make_generate_hooks_node",
    "make_intake_node",
    "make_quality_scoring_node",
    "make_validate_campaign_brief_node",
]
