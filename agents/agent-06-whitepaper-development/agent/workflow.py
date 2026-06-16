"""LangGraph workflow for Agent 06 - Whitepaper Development Agent."""
from __future__ import annotations

import math
from typing import Any, Callable
from uuid import uuid4

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from core.cost import (
    CostCeilingExceeded,
    authorize_call,
    estimate_for_stage,
    estimate_prompt_tokens,
    resolve_is_mock,
    total_cost_inr,
    usage_cost_inr,
)
from core.interfaces import BillableProviderError, LLMResponse, Telemetry
from core.interfaces.llm import LLMProvider, Tier

from .prompts import (
    angle_plan_prompt,
    build_system,
    draft_sections_prompt,
    normalize_context_prompt,
    outline_prompt,
)
from .schemas import (
    Agent06Request,
    AnglePlan,
    BillableNodeError,
    ClaimReviewReport,
    CostUsage,
    EvidenceMap,
    NormalizedContext,
    StageCost,
    WhitepaperDevelopmentPackage,
    WhitepaperDraft,
    WhitepaperOutline,
    WhitepaperSectionDraft,
)
from .scoring import build_risk_report, score_output
from .state import Agent06State
from .tools import (
    build_evidence_map,
    clean_text,
    detect_generic_content,
    extract_claims_from_draft,
    important_terms,
    split_text_items,
    supplied_context_text,
)


_ALIASES = {
    "company": "company_context",
    "company_product_context": "company_context",
    "product_context": "company_context",
    "audience": "target_audience",
    "problem_being_solved": "problem",
    "solution_description": "solution",
    "desired_tone": "tone",
    "length": "target_depth",
    "depth": "target_depth",
    "call_to_action": "cta",
    "legal_constraints": "compliance_constraints",
}

_BILLABLE_STAGES = (
    "normalize_context",
    "plan_angle",
    "generate_outline",
    "draft_sections",
)


def _node_with_error_guard(
    node_name: str,
    node_fn: Callable,
    *,
    ceiling_inr: float = math.inf,
    tel: Telemetry | None = None,
) -> Callable:
    def guarded(state: dict) -> dict[str, Any]:
        try:
            result = node_fn(state)
            new_costs = result.get("cost_usage")
            if new_costs and math.isfinite(ceiling_inr):
                prior = state.get("cost_usage") or []
                if total_cost_inr(list(prior) + list(new_costs)) > ceiling_inr:
                    return {**result, "cost_gate_ok": False}
            return result
        except CostCeilingExceeded:
            return {"cost_gate_ok": False}
        except BillableNodeError as be:
            if tel is not None:
                try:
                    tel.log("node.error", node=node_name, kind=type(be.cause).__name__)
                except Exception:
                    pass
            return {
                "cost_usage": [be.stage_cost],
                "error_state": {
                    "node": node_name,
                    "kind": type(be.cause).__name__,
                    "message": f"{type(be.cause).__name__} in {node_name}",
                },
            }
        except Exception as exc:  # noqa: BLE001
            if tel is not None:
                try:
                    tel.log("node.error", node=node_name, kind=type(exc).__name__)
                except Exception:
                    pass
            return {
                "error_state": {
                    "node": node_name,
                    "kind": type(exc).__name__,
                    "message": f"{type(exc).__name__} in {node_name}",
                }
            }

    guarded.__name__ = f"guarded_{node_name}"
    return guarded


def _safe_assemble_wrapper(assemble_fn: Callable) -> Callable:
    def safe_assemble(state: dict) -> dict[str, Any]:
        try:
            return assemble_fn(state)
        except Exception as exc:  # noqa: BLE001
            try:
                stage_costs = state.get("cost_usage", [])
                total = round(total_cost_inr(stage_costs), 6)
                cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
            except Exception:
                cost = CostUsage(stage_costs=(), total_inr=0.0)
            pkg = WhitepaperDevelopmentPackage(
                status="error",
                cost=cost,
                notes=f"Fatal error in assemble_package ({type(exc).__name__})",
            )
            return {"final_output": pkg, "status": "error"}

    safe_assemble.__name__ = "safe_assemble_package"
    return safe_assemble


def _request_from_state(state: Agent06State) -> Agent06Request:
    existing = state.get("request")
    if isinstance(existing, Agent06Request):
        return existing
    raw = state.get("raw_input")
    if isinstance(raw, Agent06Request):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("Agent 06 input must be a serialized whitepaper request")
    data = dict(raw)
    for old_key, new_key in _ALIASES.items():
        if old_key in data:
            data.setdefault(new_key, data[old_key])
    for key in (
        "proof_points",
        "source_notes",
        "differentiators",
        "objections",
        "compliance_constraints",
        "excluded_claims",
    ):
        if key in data:
            data[key] = split_text_items(data[key])
    return Agent06Request.model_validate(data)


def _safe_validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        fields = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "input"
            fields.append(loc)
        return "Missing or invalid whitepaper fields: " + ", ".join(dict.fromkeys(fields))
    return "Invalid Agent 06 input: " + type(exc).__name__


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
    state: Agent06State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[LLMResponse, StageCost]:
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs = {k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()}
    is_mock = resolve_is_mock(cfg)
    output_cpt, input_cpt, fixed, max_prompt, tier_max_output = _stage_pricing(cfg, tier)
    max_output = int(cost_cfg.get("max_output_tokens", {}).get(stage_name, tier_max_output))
    prompt_tokens_est = estimate_prompt_tokens(messages, response_schema)
    if prompt_tokens_est > max_prompt:
        raise CostCeilingExceeded(
            f"{stage_name}: prompt estimate {prompt_tokens_est} exceeds max_prompt_tokens={max_prompt}"
        )

    current_spend = total_cost_inr(state.get("cost_usage", []))
    downstream_reserve = sum(estimate_for_stage(s, estimated_costs) for s in downstream_stages)
    worst_case_inr = (prompt_tokens_est * input_cpt) + (max_output * output_cpt) + fixed
    if not is_mock and (current_spend + worst_case_inr + downstream_reserve) > ceiling_inr:
        raise CostCeilingExceeded(
            f"{stage_name}: pre-call worst-case Rs{worst_case_inr:.4f} + spent "
            f"Rs{current_spend:.4f} + downstream reserve Rs{downstream_reserve:.4f} "
            f"exceeds ceiling Rs{ceiling_inr:.2f}"
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
    if max_output > 0:
        params["max_tokens"] = (
            min(auth.max_tokens, max_output) if auth.max_tokens is not None else max_output
        )
    elif auth.max_tokens is not None:
        params["max_tokens"] = auth.max_tokens

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
    state: Agent06State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[object | None, list[StageCost], bool, bool]:
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
        return response.structured, [stage_cost], True, False
    except CostCeilingExceeded:
        _log_provider_hiccup(tel, stage_name, "cost_ceiling_preflight")
        return None, [], False, True
    except BillableNodeError as be:
        _log_provider_hiccup(tel, stage_name, type(be.cause).__name__)
        return None, [be.stage_cost], False, False
    except Exception as exc:  # noqa: BLE001
        _log_provider_hiccup(tel, stage_name, type(exc).__name__)
        return None, [], False, False


def _log_provider_hiccup(tel: Telemetry, stage_name: str, kind: str) -> None:
    try:
        tel.log(f"{stage_name}.provider_hiccup", node=stage_name, kind=kind)
    except Exception:
        pass


def _is_generic_text(value: str) -> bool:
    text = clean_text(value).lower()
    return not text or len(text) < 8 or set(text) <= {"x"}


def _normalize_fallback(request: Agent06Request) -> NormalizedContext:
    constraints = request.compliance_constraints + tuple(f"Excluded claim: {x}" for x in request.excluded_claims)
    return NormalizedContext(
        request_summary=(
            f"{request.topic} for {request.target_audience} in {request.industry}; "
            f"solution focus: {request.solution}."
        ),
        topic=request.topic,
        company_context_summary=request.company_context,
        target_audience=request.target_audience,
        industry_context=request.industry,
        problem_summary=request.problem,
        solution_summary=request.solution,
        tone=request.tone,
        target_depth=request.target_depth,
        cta=request.cta,
        constraints=constraints,
    )


def _usable_normalized(candidate: object) -> NormalizedContext | None:
    if not isinstance(candidate, NormalizedContext):
        return None
    if any(
        _is_generic_text(value)
        for value in (
            candidate.request_summary,
            candidate.company_context_summary,
            candidate.problem_summary,
            candidate.solution_summary,
        )
    ):
        return None
    return candidate


def _angle_fallback(request: Agent06Request, normalized: NormalizedContext) -> AnglePlan:
    topic = normalized.topic
    audience = normalized.target_audience
    titles = (
        f"{topic}: A Practical Whitepaper for {audience}",
        f"How {request.solution} Addresses {request.problem}",
        f"{request.industry} Whitepaper: From {request.problem} to {request.solution}",
    )
    return AnglePlan(
        recommended_angle=(
            f"Frame {request.solution} as a practical response to {request.problem} for "
            f"{audience}, using supplied proof points where available and clearly marking evidence gaps."
        ),
        audience_promise=(
            f"Help {audience} understand the business problem, evaluate the proposed solution, "
            "and identify what evidence must be verified before action."
        ),
        narrative_thesis=(
            f"The whitepaper should connect the {request.industry} context, the buyer pain, "
            f"and the concrete role of {request.solution} without unsupported market claims."
        ),
        title_options=titles,
    )


def _usable_angle(candidate: object) -> AnglePlan | None:
    if not isinstance(candidate, AnglePlan):
        return None
    if len(candidate.title_options) < 3:
        return None
    if _is_generic_text(candidate.recommended_angle):
        return None
    return candidate


def _outline_fallback(
    request: Agent06Request,
    angle: AnglePlan,
    evidence_map: EvidenceMap,
) -> WhitepaperOutline:
    sections = (
        ("exec-summary", "Executive Summary", angle.narrative_thesis),
        ("audience", "Target Audience and Reader Pain Points", request.target_audience),
        ("problem", "Problem Statement", request.problem),
        ("industry", "Industry and Context", request.industry),
        ("solution", "Proposed Solution", request.solution),
        ("benefits", "Benefits", "Business benefits tied to supplied proof points."),
        ("use-cases", "Use Cases", "Practical usage scenarios from supplied context."),
        ("implementation", "Implementation Approach", "How a team could adopt the solution."),
        ("risks", "Risks and Challenges", "Risks, objections, constraints, and missing evidence."),
        ("conclusion", "Conclusion and CTA", request.cta),
    )
    return WhitepaperOutline(
        sections=tuple(
            {
                "section_id": section_id,
                "heading": heading,
                "purpose": purpose,
                "key_points": (
                    purpose,
                    "Use supplied context only; avoid unsupported claims.",
                ),
                "evidence_needed": evidence_map.missing_evidence,
            }
            for section_id, heading, purpose in sections
        )
    )


def _usable_outline(candidate: object) -> WhitepaperOutline | None:
    if not isinstance(candidate, WhitepaperOutline):
        return None
    headings = {section.heading.lower() for section in candidate.sections}
    required_tokens = ("executive", "problem", "solution", "benefit", "implementation", "risk")
    if not all(any(token in heading for heading in headings) for token in required_tokens):
        return None
    if any(_is_generic_text(section.heading) or _is_generic_text(section.purpose) for section in candidate.sections):
        return None
    return candidate


def _draft_fallback(
    request: Agent06Request,
    normalized: NormalizedContext,
    angle: AnglePlan,
    evidence_map: EvidenceMap,
    outline: WhitepaperOutline,
) -> WhitepaperDraft:
    proof_sentence = (
        "Supplied proof points to incorporate after verification: " + "; ".join(request.proof_points) + "."
        if request.proof_points
        else "Quantified proof points are not supplied, so any impact claims must remain qualitative until reviewed."
    )
    source_sentence = (
        "Source notes supplied for reviewer follow-up: " + "; ".join(request.source_notes) + "."
        if request.source_notes
        else "No source notes were supplied; reviewers should add approved references before publication."
    )
    differentiator_sentence = (
        "Differentiators to emphasize: " + "; ".join(request.differentiators) + "."
        if request.differentiators
        else "Specific differentiators are missing and should be added before final approval."
    )
    objection_sentence = (
        "Known objections to address: " + "; ".join(request.objections) + "."
        if request.objections
        else "Buyer objections were not supplied; reviewers should add likely adoption blockers."
    )
    compliance_sentence = (
        "Compliance/legal constraints: " + "; ".join(request.compliance_constraints) + "."
        if request.compliance_constraints
        else "No compliance or legal constraints were supplied; human review is still required before publication."
    )

    executive = (
        f"This draft whitepaper package frames {request.topic} for {request.target_audience} in "
        f"{request.industry}. It positions {request.solution} as a response to {request.problem}, "
        f"grounded in the supplied company/product context: {normalized.company_context_summary}. "
        f"{proof_sentence}"
    )
    audience = (
        f"The primary reader is {request.target_audience}. Their pain points center on {request.problem}, "
        "the need to evaluate a credible solution path, and the need for evidence that can survive internal review. "
        f"The tone should remain {request.tone}, with depth set to {request.target_depth}."
    )
    problem = (
        f"The core problem is {request.problem}. In the context of {request.industry}, the whitepaper should "
        "explain why this problem matters operationally, where it creates decision friction, and what information "
        "a buyer needs before trusting a proposed solution."
    )
    industry = (
        f"The industry/context section should stay anchored to the supplied context rather than external market data. "
        f"For {request.industry}, it should explain the practical environment around {request.topic}, identify where "
        f"{request.target_audience} feels the problem, and mark any broader market claims as evidence gaps. "
        f"{source_sentence}"
    )
    solution = (
        f"The proposed solution is {request.solution}. The section should connect the solution mechanics to the "
        f"reader's problem, explain what changes for the team, and avoid claiming verified results unless the user "
        "has supplied proof. "
        f"{differentiator_sentence}"
    )
    benefits = (
        f"Benefits should be presented as review-ready hypotheses tied to the supplied context: clearer decision-making, "
        f"better handling of {request.problem}, and a more structured path for adopting {request.solution}. "
        f"{proof_sentence}"
    )
    use_cases = (
        f"Use cases should focus on situations where {request.target_audience} is actively dealing with {request.problem}. "
        "Each use case should state the business situation, how the solution is applied, and what evidence reviewers "
        "need to validate the expected outcome."
    )
    implementation = (
        f"Implementation should outline discovery, stakeholder alignment, pilot scoping, rollout planning, evidence capture, "
        f"and review checkpoints for {request.solution}. The section should give marketing and content teams enough detail "
        "to brief subject matter experts without pretending deployment details are already verified."
    )
    risks = (
        f"Risks and challenges include missing evidence, buyer skepticism, implementation assumptions, and any constraints "
        f"that affect claims. {objection_sentence} {compliance_sentence}"
    )
    conclusion = (
        f"The conclusion should restate the thesis: {request.solution} can be positioned as a practical answer to "
        f"{request.problem} for {request.target_audience}, but the final whitepaper must be reviewed and evidence-completed "
        "before publication."
    )
    cta = f"Recommended CTA: {request.cta}. Keep it human-approved and do not trigger external actions in v1."

    section_lookup = {
        "exec-summary": executive,
        "audience": audience,
        "problem": problem,
        "industry": industry,
        "solution": solution,
        "benefits": benefits,
        "use-cases": use_cases,
        "implementation": implementation,
        "risks": risks,
        "conclusion": conclusion + " " + cta,
    }
    sections = tuple(
        WhitepaperSectionDraft(
            section_id=section.section_id,
            heading=section.heading,
            body=section_lookup.get(section.section_id, section.purpose),
        )
        for section in outline.sections
    )
    return WhitepaperDraft(
        executive_summary=executive,
        target_audience_and_pain_points=audience,
        problem_statement=problem,
        industry_context=industry,
        proposed_solution=solution,
        benefits=benefits,
        use_cases=use_cases,
        implementation_approach=implementation,
        risks_and_challenges=risks,
        conclusion=conclusion,
        cta=cta,
        sections=sections,
    )


def _usable_draft(candidate: object, request: Agent06Request) -> WhitepaperDraft | None:
    if not isinstance(candidate, WhitepaperDraft):
        return None
    text = " ".join(
        (
            candidate.executive_summary,
            candidate.problem_statement,
            candidate.proposed_solution,
            candidate.benefits,
            candidate.implementation_approach,
        )
    )
    if _is_generic_text(text):
        return None
    # Grounding gate: the draft must actually use the supplied topic/problem/
    # solution/audience/differentiator vocabulary. Use meaningful term overlap
    # (robust to paraphrase) rather than literal field-prefix matching. The old
    # prefix check (`request.topic[:12] in text`) rewarded verbatim copying and
    # rejected well-written, paraphrased drafts — silently discarding genuine LLM
    # output in favour of the deterministic fallback. This gate only decides
    # LLM-vs-fallback; the downstream generic-content/scoring/risk gates still
    # evaluate whichever draft is selected, so accepting real prose here does not
    # weaken any quality check.
    lowered = text.lower()
    terms = important_terms(request)
    if terms:
        hits = sum(1 for term in terms if term in lowered)
        if hits < min(3, len(terms)):
            return None
    return candidate


def make_intake_validate_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def intake(state: Agent06State) -> dict[str, Any]:
        request_id = state.get("request_id") or uuid4().hex
        try:
            request = _request_from_state(state)
        except Exception as exc:  # noqa: BLE001
            message = _safe_validation_message(exc)
            with tel.span("intake_validate") as span_id:
                tel.log("intake_validate.invalid", span_id=span_id)
            return {
                "request_id": request_id,
                "status": "needs_more_input",
                "validation_errors": (message,),
                "notes": message,
            }
        with tel.span("intake_validate") as span_id:
            tel.log("intake_validate.accepted", span_id=span_id)
        return {"request_id": request_id, "request": request, "status": "running", "validation_errors": ()}

    return intake


def make_normalize_context_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def normalize(state: Agent06State) -> dict[str, Any]:
        request = state["request"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": normalize_context_prompt(request)},
        ]
        tier = _stage_tier(cfg, "normalize_context", "cheap")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="normalize_context",
            tier=tier,
            messages=messages,
            downstream_stages=("plan_angle", "generate_outline", "draft_sections"),
            response_schema=NormalizedContext,
        )
        candidate = _usable_normalized(structured)
        normalized = candidate or _normalize_fallback(request)
        return {
            "normalized_context": normalized,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return normalize


def make_plan_angle_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def plan(state: Agent06State) -> dict[str, Any]:
        request = state["request"]
        normalized = state["normalized_context"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": angle_plan_prompt(request, normalized)},
        ]
        tier = _stage_tier(cfg, "plan_angle", "cheap")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="plan_angle",
            tier=tier,
            messages=messages,
            downstream_stages=("generate_outline", "draft_sections"),
            response_schema=AnglePlan,
        )
        candidate = _usable_angle(structured)
        angle = candidate or _angle_fallback(request, normalized)
        return {
            "angle_plan": angle,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return plan


def make_map_evidence_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def map_evidence(state: Agent06State) -> dict[str, Any]:
        evidence_map = build_evidence_map(state["request"])
        with tel.span("map_evidence") as span_id:
            tel.log("map_evidence.complete", span_id=span_id, evidence_count=len(evidence_map.evidence_items))
        return {"evidence_map": evidence_map}

    return map_evidence


def make_generate_outline_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def outline_node(state: Agent06State) -> dict[str, Any]:
        request = state["request"]
        normalized = state["normalized_context"]
        angle = state["angle_plan"]
        evidence_map = state["evidence_map"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": outline_prompt(request, normalized, angle, evidence_map)},
        ]
        tier = _stage_tier(cfg, "generate_outline", "cheap")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="generate_outline",
            tier=tier,
            messages=messages,
            downstream_stages=("draft_sections",),
            response_schema=WhitepaperOutline,
        )
        candidate = _usable_outline(structured)
        outline = candidate or _outline_fallback(request, angle, evidence_map)
        return {
            "outline": outline,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return outline_node


def make_draft_sections_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def draft_node(state: Agent06State) -> dict[str, Any]:
        request = state["request"]
        normalized = state["normalized_context"]
        angle = state["angle_plan"]
        evidence_map = state["evidence_map"]
        outline = state["outline"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": draft_sections_prompt(request, normalized, angle, evidence_map, outline)},
        ]
        tier = _stage_tier(cfg, "draft_sections", "strong")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="draft_sections",
            tier=tier,
            messages=messages,
            response_schema=WhitepaperDraft,
        )
        candidate = _usable_draft(structured, request)
        draft = candidate or _draft_fallback(request, normalized, angle, evidence_map, outline)
        return {
            "draft": draft,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return draft_node


def make_review_claims_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def review(state: Agent06State) -> dict[str, Any]:
        claims, unsupported, forbidden = extract_claims_from_draft(
            state.get("draft"),
            state.get("evidence_map"),
            supplied_context_text(state.get("request")),
        )
        report = ClaimReviewReport(
            key_claims=claims,
            unsupported_claims=unsupported,
            fabricated_or_forbidden_claims=forbidden,
        )
        with tel.span("review_claims") as span_id:
            tel.log("review_claims.complete", span_id=span_id, claim_count=len(claims))
        return {"claim_review": report}

    return review


def make_detect_generic_content_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def detect(state: Agent06State) -> dict[str, Any]:
        report = detect_generic_content(request=state.get("request"), draft=state.get("draft"))
        with tel.span("detect_generic_content") as span_id:
            tel.log("detect_generic_content.complete", span_id=span_id, generic_flags=len(report.flags))
        return {"generic_report": report}

    return detect


def make_score_quality_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def score_node(state: Agent06State) -> dict[str, Any]:
        risks = build_risk_report(
            request=state.get("request"),
            validation_errors=state.get("validation_errors", ()),
            draft=state.get("draft"),
            outline=state.get("outline"),
            evidence_map=state.get("evidence_map"),
            claim_review=state.get("claim_review"),
            generic_report=state.get("generic_report"),
        )
        score = score_output(
            request=state.get("request"),
            outline=state.get("outline"),
            draft=state.get("draft"),
            evidence_map=state.get("evidence_map"),
            claim_review=state.get("claim_review"),
            generic_report=state.get("generic_report"),
            risk_report=risks,
            validation_errors=state.get("validation_errors", ()),
        )
        with tel.span("score_quality") as span_id:
            tel.metric("quality.overall_score", score.total_score, node="score_quality")
            tel.log("score_quality.complete", span_id=span_id, score=score.total_score)
        return {"risk_report": risks, "quality_score": score}

    return score_node


def make_assemble_package_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 50.0))

    def assemble(state: Agent06State) -> dict[str, Any]:
        stage_costs = list(state.get("cost_usage", []))
        total = round(total_cost_inr(stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
        status = _determine_status(state, total=total, ceiling_inr=ceiling_inr)
        notes = _determine_notes(state, status)
        draft = state.get("draft")
        angle = state.get("angle_plan")
        evidence = state.get("evidence_map")
        claims = state.get("claim_review")
        risks = state.get("risk_report")
        generic = state.get("generic_report")
        score = state.get("quality_score")
        package = WhitepaperDevelopmentPackage(
            status=status,  # type: ignore[arg-type]
            package_id=state.get("request_id", ""),
            request_summary=_request_summary(state.get("request")),
            title_options=angle.title_options if angle else (),
            recommended_angle=angle.recommended_angle if angle else "",
            executive_summary=draft.executive_summary if draft else "",
            target_audience_and_pain_points=draft.target_audience_and_pain_points if draft else "",
            problem_statement=draft.problem_statement if draft else "",
            industry_context=draft.industry_context if draft else "",
            proposed_solution=draft.proposed_solution if draft else "",
            benefits=draft.benefits if draft else "",
            use_cases=draft.use_cases if draft else "",
            implementation_approach=draft.implementation_approach if draft else "",
            risks_and_challenges=draft.risks_and_challenges if draft else "",
            conclusion=draft.conclusion if draft else "",
            cta=draft.cta if draft else "",
            key_claims=claims.key_claims if claims else (),
            missing_evidence=evidence.missing_evidence if evidence else (),
            missing_inputs=evidence.missing_inputs if evidence else (),
            risk_flags=risks.risk_flags if risks else (),
            generic_content_flags=generic.flags if generic else (),
            quality_score=score,
            pass_status="pass" if score and score.passed else "fail",
            improvement_suggestions=_improvement_suggestions(state, status),
            cost=cost,
            notes=notes,
            generation_used_llm=bool(state.get("generation_used_llm", False)),
        )
        with tel.span("assemble_package") as span_id:
            tel.metric("total.cost_inr", total, node="assemble_package")
            tel.log("assemble_package.complete", span_id=span_id, status=status)
        return {"status": status, "cost": cost, "final_output": package}

    return assemble


def _request_summary(request: Agent06Request | None) -> str:
    if request is None:
        return ""
    return (
        f"{request.topic} for {request.target_audience}; industry: {request.industry}; "
        f"solution: {request.solution}."
    )


def _determine_status(state: Agent06State, *, total: float, ceiling_inr: float) -> str:
    if not state.get("cost_gate_ok", True) or total > ceiling_inr:
        return "stopped_cost_ceiling"
    if state.get("error_state") is not None:
        return "error"
    if state.get("status") == "needs_more_input":
        return "needs_more_input"
    if state.get("budget_limited"):
        return "needs_review_budget_limited"
    score = state.get("quality_score")
    if score is not None and score.passed:
        return "pass"
    return "needs_human"


def _determine_notes(state: Agent06State, status: str) -> str:
    if status == "stopped_cost_ceiling":
        return "Cost ceiling reached; run stopped before generating more whitepaper output."
    if status == "error":
        error = state.get("error_state", {})
        return f"Error in {error.get('node', 'unknown')} ({error.get('kind', 'Error')})"
    if status == "needs_more_input":
        return state.get("notes", "Whitepaper request needs required fields.")
    if status == "needs_review_budget_limited":
        return (
            "Budget limit reached: one or more stages used deterministic fallbacks to stay under the "
            "cost ceiling. Review and optionally re-run with a smaller target depth for richer live output."
        )
    if status == "pass":
        return "Review-ready draft whitepaper development package generated. Human approval is still required before publication."
    risks = state.get("risk_report")
    if risks and risks.hard_fail_codes:
        return "Hard-fail whitepaper risks require human review: " + ", ".join(risks.hard_fail_codes)
    return "Whitepaper package did not pass the quality threshold; review improvement suggestions."


def _improvement_suggestions(state: Agent06State, status: str) -> tuple[str, ...]:
    suggestions: list[str] = []
    if status == "needs_more_input":
        return tuple(state.get("validation_errors", ()))
    evidence = state.get("evidence_map")
    if evidence and evidence.missing_evidence:
        suggestions.extend(f"Add evidence: {item}" for item in evidence.missing_evidence)
    risks = state.get("risk_report")
    if risks:
        suggestions.extend(flag.recommended_fix or flag.message for flag in risks.risk_flags)
    generic = state.get("generic_report")
    if generic:
        suggestions.extend(flag.recommended_fix or flag.message for flag in generic.flags)
    suggestions.append(
        "Human review is required before publication; verify evidence, claims, legal constraints, and final positioning."
    )
    return tuple(dict.fromkeys(item for item in suggestions if item))


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 06's cloud-neutral LangGraph workflow."""
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 50.0))
    nodes = {
        "intake_validate": _node_with_error_guard(
            "intake_validate", make_intake_validate_node(cfg, llm, tel), tel=tel
        ),
        "normalize_context": _node_with_error_guard(
            "normalize_context", make_normalize_context_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "plan_angle": _node_with_error_guard(
            "plan_angle", make_plan_angle_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "map_evidence": _node_with_error_guard(
            "map_evidence", make_map_evidence_node(cfg, llm, tel), tel=tel
        ),
        "generate_outline": _node_with_error_guard(
            "generate_outline", make_generate_outline_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "draft_sections": _node_with_error_guard(
            "draft_sections", make_draft_sections_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "review_claims": _node_with_error_guard(
            "review_claims", make_review_claims_node(cfg, llm, tel), tel=tel
        ),
        "detect_generic_content": _node_with_error_guard(
            "detect_generic_content", make_detect_generic_content_node(cfg, llm, tel), tel=tel
        ),
        "score_quality": _node_with_error_guard(
            "score_quality", make_score_quality_node(cfg, llm, tel), tel=tel
        ),
        "assemble_package": _safe_assemble_wrapper(make_assemble_package_node(cfg, llm, tel)),
    }

    def _emit_route(node: str, decision: str, target: str) -> None:
        try:
            tel.log("route.decision", node=node, decision=decision, target=target)
        except Exception:
            pass

    def route_basic(node: str, target: str):
        def route(state: Agent06State) -> str:
            if state.get("error_state") is not None:
                _emit_route(node, "error", "assemble_package")
                return "assemble_package"
            if not state.get("cost_gate_ok", True):
                _emit_route(node, "cost_ceiling", "assemble_package")
                return "assemble_package"
            _emit_route(node, "ok", target)
            return target

        return route

    def route_after_intake(state: Agent06State) -> str:
        if state.get("error_state") is not None:
            _emit_route("intake_validate", "error", "assemble_package")
            return "assemble_package"
        if state.get("status") == "needs_more_input":
            _emit_route("intake_validate", "needs_more_input", "assemble_package")
            return "assemble_package"
        _emit_route("intake_validate", "ok", "normalize_context")
        return "normalize_context"

    graph = StateGraph(Agent06State)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.set_entry_point("intake_validate")
    edges = (
        ("normalize_context", "plan_angle"),
        ("plan_angle", "map_evidence"),
        ("map_evidence", "generate_outline"),
        ("generate_outline", "draft_sections"),
        ("draft_sections", "review_claims"),
        ("review_claims", "detect_generic_content"),
        ("detect_generic_content", "score_quality"),
        ("score_quality", "assemble_package"),
    )
    graph.add_conditional_edges(
        "intake_validate",
        route_after_intake,
        {"normalize_context": "normalize_context", "assemble_package": "assemble_package"},
    )
    for source, target in edges:
        graph.add_conditional_edges(
            source,
            route_basic(source, target),
            {target: target, "assemble_package": "assemble_package"},
        )
    graph.add_edge("assemble_package", END)
    return graph.compile()


__all__ = ["build_graph"]
