"""LangGraph workflow for Agent 07 - Case Study Generation Agent."""
from __future__ import annotations

import math
from typing import Any, Callable
from uuid import uuid4

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from core.cost import CostCeilingExceeded, estimate_for_stage, estimate_prompt_tokens, resolve_is_mock, total_cost_inr, usage_cost_inr
from core.interfaces import BillableProviderError, LLMResponse, Telemetry
from core.interfaces.llm import LLMProvider, Tier

from .prompts import build_system, draft_prompt, plan_prompt
from .schemas import (
    Agent07Status,
    BillableNodeError,
    CaseStudyDraft,
    CaseStudyPackage,
    CaseStudyPlan,
    CaseStudyRequest,
    CostUsage,
    EvidenceMap,
    MissingInfoWarning,
    NormalizedCaseStudyContext,
    OutlineSection,
    QualityDimensionScore,
    QualityReport,
    QuoteCtaPackage,
    RiskFlag,
    StageCost,
)
from .scoring import determine_status, score_case_study_quality
from .state import Agent07State
from .tools import (
    build_evidence_map,
    build_missing_information_warnings,
    build_risk_flags,
    clean_text,
    detect_generic_content,
    important_terms,
    split_text_items,
    supplied_context_text,
    word_count,
)


_ALIASES = {
    "customer": "customer_name",
    "company": "customer_name",
    "company_name": "customer_name",
    "audience": "target_audience",
    "problem": "challenge",
    "business_problem": "challenge",
    "solution": "solution_summary",
    "solution_used": "solution_summary",
    "product": "product_or_service",
    "service": "product_or_service",
    "outcomes": "results",
    "outcome_notes": "results",
    "results_outcomes": "results",
    "quotes": "customer_quotes",
    "cta": "cta_goal",
    "notes": "source_notes",
}

_BILLABLE_STAGES = ("plan_case_study", "draft_case_study")


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
            return {"cost_gate_ok": False, "budget_limited": True}
        except BillableNodeError as be:
            _safe_log(tel, "node.error", node=node_name, kind=type(be.cause).__name__)
            return {
                "cost_usage": [be.stage_cost],
                "error_state": {
                    "node": node_name,
                    "kind": type(be.cause).__name__,
                    "message": f"{type(be.cause).__name__} in {node_name}",
                },
            }
        except Exception as exc:  # noqa: BLE001
            _safe_log(tel, "node.error", node=node_name, kind=type(exc).__name__)
            return {
                "error_state": {
                    "node": node_name,
                    "kind": type(exc).__name__,
                    "message": f"{type(exc).__name__} in {node_name}",
                }
            }

    guarded.__name__ = f"guarded_{node_name}"
    return guarded


def _safe_log(tel: Telemetry | None, event: str, **kwargs: Any) -> None:
    if tel is None:
        return
    try:
        tel.log(event, **kwargs)
    except Exception:
        pass


def _safe_assemble_wrapper(assemble_fn: Callable) -> Callable:
    def safe_assemble(state: dict) -> dict[str, Any]:
        try:
            return assemble_fn(state)
        except Exception as exc:  # noqa: BLE001
            try:
                ceiling = float(state.get("cost_ceiling_inr", 25.0))
                stage_costs = state.get("cost_usage", [])
                total = round(total_cost_inr(stage_costs), 6)
                cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total, cost_ceiling_inr=ceiling)
            except Exception:
                cost = CostUsage(stage_costs=(), total_inr=0.0, cost_ceiling_inr=25.0)
            quality = _zero_quality(f"Fatal error in assemble_package ({type(exc).__name__})")
            package = CaseStudyPackage(
                request_id=state.get("request_id") or uuid4().hex,
                status="reject",
                pass_status="fail",
                quality_report=quality,
                cost_usage=cost,
                notes=f"Fatal error in assemble_package ({type(exc).__name__})",
            )
            return {"final_output": package, "status": "reject"}

    safe_assemble.__name__ = "safe_assemble_package"
    return safe_assemble


def _request_from_state(state: Agent07State) -> CaseStudyRequest:
    existing = state.get("request")
    if isinstance(existing, CaseStudyRequest):
        return existing
    raw = state.get("raw_input")
    if isinstance(raw, CaseStudyRequest):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("Agent 07 input must be a serialized case study request")
    data = dict(raw)
    for old_key, new_key in _ALIASES.items():
        if old_key in data:
            data.setdefault(new_key, data[old_key])
    if "customer_quotes" in data:
        data["customer_quotes"] = split_text_items(data["customer_quotes"])
    return CaseStudyRequest.model_validate(data)


def _safe_validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        fields = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "input"
            fields.append(loc)
        return "Missing or invalid case study fields: " + ", ".join(dict.fromkeys(fields))
    return "Invalid Agent 07 input: " + type(exc).__name__


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


def _cost_ceiling(cfg: dict, request: CaseStudyRequest | None = None) -> float:
    configured = float(cfg.get("cost", {}).get("ceiling_inr", 25.0))
    if request is not None and request.max_cost_rs is not None:
        return min(configured, float(request.max_cost_rs))
    return configured


def _billable_llm_call(
    *,
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    state: Agent07State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[LLMResponse, StageCost]:
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr = _cost_ceiling(cfg, state.get("request"))
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
    current_stage_reserve = estimate_for_stage(stage_name, estimated_costs)
    downstream_reserve = sum(estimate_for_stage(stage, estimated_costs) for stage in downstream_stages)
    worst_case_inr = (prompt_tokens_est * input_cpt) + (max_output * output_cpt) + fixed
    budgeted_worst_case = max(worst_case_inr, current_stage_reserve)
    if not is_mock and (current_spend + budgeted_worst_case + downstream_reserve) > ceiling_inr:
        raise CostCeilingExceeded(
            f"{stage_name}: worst-case call plus downstream reserve exceeds ceiling Rs {ceiling_inr:.2f}"
        )

    params: dict[str, Any] = {"_authorized_prompt_tokens": prompt_tokens_est}
    if max_output > 0:
        params["max_tokens"] = max_output

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
    state: Agent07State,
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
        _safe_log(tel, f"{stage_name}.provider_hiccup", node=stage_name, kind="cost_ceiling_preflight")
        return None, [], False, True
    except BillableNodeError as be:
        _safe_log(tel, f"{stage_name}.provider_hiccup", node=stage_name, kind=type(be.cause).__name__)
        return None, [be.stage_cost], False, False
    except Exception as exc:  # noqa: BLE001
        _safe_log(tel, f"{stage_name}.provider_hiccup", node=stage_name, kind=type(exc).__name__)
        return None, [], False, False


def _is_generic_text(value: str) -> bool:
    text = clean_text(value).lower()
    return not text or len(text) < 8 or set(text) <= {"x"}


def _normalize_fallback(request: CaseStudyRequest) -> NormalizedCaseStudyContext:
    customer_label = (
        "Anonymized customer"
        if request.anonymize_customer or not request.customer_name
        else request.customer_name
    )
    public_usage = (
        "Anonymized customer usage required until public approval is confirmed."
        if request.anonymize_customer or not request.customer_name
        else "Named customer usage supplied by requester; human approval still required before publication."
    )
    return NormalizedCaseStudyContext(
        customer_label=customer_label,
        public_customer_usage=public_usage,
        industry=request.industry,
        target_audience=request.target_audience,
        challenge_summary=request.challenge,
        solution_summary=request.solution_summary,
        results_summary=request.results,
        implementation_summary=request.implementation_notes or "Implementation detail was not supplied; keep this section review-oriented.",
        tone=request.tone,
        cta_goal=request.cta_goal or "Invite the reader to request a related consultation.",
        confidentiality_note=(
            "Use anonymized language until customer approval is documented."
            if request.anonymize_customer
            else ""
        ),
    )


def _plan_fallback(
    request: CaseStudyRequest,
    normalized: NormalizedCaseStudyContext,
    evidence: EvidenceMap,
) -> CaseStudyPlan:
    customer = normalized.customer_label
    solution_name = request.product_or_service or "the solution"
    metrics_hint = (
        f"Use supplied metrics such as {evidence.metric_highlights[0].value}."
        if evidence.metric_highlights
        else "Keep outcome claims qualitative until metrics are supplied."
    )
    title_options = (
        f"How {customer} Addressed {request.challenge[:70].rstrip()}",
        f"{customer} Case Study: From Challenge to Measurable Progress",
        f"How {solution_name} Helped {customer} Improve {request.industry} Outcomes",
    )
    sections = (
        OutlineSection(
            section_id="executive-summary",
            heading="Executive Summary",
            purpose="Summarize the customer, challenge, solution, and results.",
            evidence_needed=evidence.missing_evidence,
        ),
        OutlineSection(
            section_id="customer-background",
            heading="Customer Background",
            purpose="Explain who the customer is and why the story matters to the target audience.",
        ),
        OutlineSection(
            section_id="challenge",
            heading="Challenge",
            purpose="Describe the business problem in concrete terms.",
        ),
        OutlineSection(
            section_id="solution",
            heading="Solution",
            purpose="Connect the supplied product or service to the customer challenge.",
        ),
        OutlineSection(
            section_id="implementation",
            heading="Implementation",
            purpose="Describe process, rollout, stakeholders, and missing implementation evidence.",
            evidence_needed=("Implementation/process detail.",) if not request.implementation_notes else (),
        ),
        OutlineSection(
            section_id="results",
            heading="Results",
            purpose="Present outcomes using supplied evidence only. " + metrics_hint,
            evidence_needed=evidence.missing_evidence,
        ),
        OutlineSection(
            section_id="cta",
            heading="CTA",
            purpose="Suggest a next step aligned to the campaign or sales goal.",
        ),
    )
    return CaseStudyPlan(
        story_angle=(
            f"Frame the story as a credible {request.industry} customer proof asset for "
            f"{request.target_audience}, centered on the move from {request.challenge} to "
            f"{request.results}."
        ),
        narrative_thesis=(
            f"{customer} faced {request.challenge}; the supplied solution helped create "
            f"{request.results}, with missing evidence clearly marked for human review."
        ),
        recommended_title=title_options[1],
        title_options=title_options,
        outline_sections=sections,
    )


def _usable_plan(candidate: object) -> CaseStudyPlan | None:
    if not isinstance(candidate, CaseStudyPlan):
        return None
    if len(candidate.title_options) < 3 or len(candidate.outline_sections) < 6:
        return None
    if any(_is_generic_text(value) for value in (candidate.story_angle, candidate.narrative_thesis, candidate.recommended_title)):
        return None
    return candidate


def _metrics_sentence(evidence: EvidenceMap) -> str:
    if not evidence.metric_highlights:
        return (
            "No quantified metrics were supplied, so this draft keeps result language qualitative "
            "and asks reviewers to add baseline, after-state, and source details."
        )
    parts = []
    for metric in evidence.metric_highlights[:4]:
        source = f" ({metric.evidence})" if metric.evidence else ""
        parts.append(f"{metric.label}: {metric.value}{source}")
    return "Supplied metric highlights for review: " + "; ".join(parts) + "."


def _draft_fallback(
    request: CaseStudyRequest,
    normalized: NormalizedCaseStudyContext,
    evidence: EvidenceMap,
    plan: CaseStudyPlan,
) -> CaseStudyDraft:
    customer = normalized.customer_label
    solution_name = request.product_or_service or "the solution"
    metric_sentence = _metrics_sentence(evidence)
    quote_sentence = (
        "Supplied quote to verify before publication: " + " ".join(request.customer_quotes[:1])
        if request.customer_quotes
        else "No approved customer quote was supplied, so quote areas remain placeholders for reviewer follow-up."
    )
    executive = (
        f"{customer} needed a clearer way to address {request.challenge}. For {request.target_audience}, "
        f"the story shows how {solution_name} supported the move from that challenge toward {request.results}. "
        f"{metric_sentence} This package is review-ready but not publication-approved."
    )
    background = (
        f"{customer} operates in {request.industry} and represents the kind of organization that "
        f"{request.target_audience} can recognize. The draft should keep customer details limited to "
        f"what was supplied and should preserve anonymization requirements where applicable. "
        f"{normalized.public_customer_usage}"
    )
    challenge = (
        f"The core challenge was {request.challenge}. The issue matters because it affects how "
        f"{request.target_audience} evaluate priorities, allocate effort, and trust a proposed path forward. "
        "Reviewers should add direct interview evidence where the problem needs more color."
    )
    solution = (
        f"The proposed solution was {request.solution_summary}. In the case study narrative, "
        f"{solution_name} should be described through concrete mechanisms from the supplied notes rather "
        "than broad marketing claims. Any customer approval, compliance, or ROI statement must stay marked "
        "as needing evidence unless the requester supplied it."
    )
    implementation = (
        f"The implementation section should explain how the work happened: {normalized.implementation_summary}. "
        "If the process involved phases, stakeholders, integrations, or timeline details, those should be "
        "added before final approval. This section is intentionally cautious so the draft does not invent a rollout."
    )
    results = (
        f"The result story is {request.results}. {metric_sentence} The draft should separate confirmed "
        "metrics from qualitative outcomes and should avoid implying external verification. "
        f"{quote_sentence}"
    )
    cta = (
        f"CTA: {normalized.cta_goal}. The final asset can invite {request.target_audience} to compare "
        "their own challenge with this story, request a consultation, or review a related proof asset."
    )
    markdown = "\n\n".join(
        (
            f"# {plan.recommended_title}",
            "## Executive Summary\n" + executive,
            "## Customer Background\n" + background,
            "## Challenge\n" + challenge,
            "## Solution\n" + solution,
            "## Implementation\n" + implementation,
            "## Results\n" + results,
            "## Next Step\n" + cta,
        )
    )
    return CaseStudyDraft(
        executive_summary=executive,
        customer_background=background,
        challenge_section=challenge,
        solution_section=solution,
        implementation_section=implementation,
        results_section=results,
        cta_section=cta,
        final_markdown_draft=markdown,
    )


def _usable_draft(candidate: object, request: CaseStudyRequest) -> CaseStudyDraft | None:
    if not isinstance(candidate, CaseStudyDraft):
        return None
    text = "\n".join(
        (
            candidate.executive_summary,
            candidate.challenge_section,
            candidate.solution_section,
            candidate.results_section,
            candidate.final_markdown_draft,
        )
    )
    if _is_generic_text(text) or word_count(text) < 180:
        return None
    terms = important_terms(request)
    lowered = text.lower()
    if terms:
        hits = sum(1 for term in terms if term in lowered)
        if hits < min(3, len(terms)):
            return None
    return candidate


def _quote_cta_fallback(
    request: CaseStudyRequest,
    normalized: NormalizedCaseStudyContext,
    evidence: EvidenceMap,
) -> QuoteCtaPackage:
    pull_quotes = (
        f"{normalized.customer_label} moved from {request.challenge} toward {request.results}.",
    )
    placeholders = (
        ()
        if request.customer_quotes
        else (
            "Customer quote needed: describe the challenge in the customer's own words.",
            "Customer quote needed: describe the most credible result or operational change.",
        )
    )
    metric_cta = (
        "Review the supplied metric evidence and approve the result claim."
        if evidence.metric_highlights
        else "Add a quantified result metric before using this as a public proof asset."
    )
    return QuoteCtaPackage(
        pull_quotes=pull_quotes,
        customer_quote_placeholders=placeholders,
        cta_suggestions=(
            normalized.cta_goal,
            metric_cta,
            "Route this package to sales or marketing review for claim and quote approval.",
        ),
    )


def make_intake_request_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def intake(state: Agent07State) -> dict[str, Any]:
        request_id = state.get("request_id") or uuid4().hex
        try:
            request = _request_from_state(state)
        except Exception as exc:  # noqa: BLE001
            message = _safe_validation_message(exc)
            with tel.span("intake_request") as span_id:
                tel.log("intake_request.invalid", span_id=span_id)
            return {
                "request_id": request_id,
                "status": "reject",
                "validation_errors": (message,),
                "notes": message,
            }
        with tel.span("intake_request") as span_id:
            tel.log("intake_request.accepted", span_id=span_id)
        return {
            "request_id": request_id,
            "request": request,
            "status": "running",
            "validation_errors": (),
            "cost_ceiling_inr": _cost_ceiling(cfg, request),
        }

    return intake


def make_normalize_input_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def normalize(state: Agent07State) -> dict[str, Any]:
        normalized = _normalize_fallback(state["request"])
        with tel.span("normalize_input") as span_id:
            tel.log("normalize_input.complete", span_id=span_id)
        return {"normalized_context": normalized}

    return normalize


def make_extract_evidence_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def extract(state: Agent07State) -> dict[str, Any]:
        evidence = build_evidence_map(state["request"])
        warnings = build_missing_information_warnings(state["request"], evidence)
        with tel.span("extract_evidence_and_metrics") as span_id:
            tel.log(
                "extract_evidence_and_metrics.complete",
                span_id=span_id,
                metric_count=len(evidence.metric_highlights),
            )
        return {"evidence_map": evidence, "missing_information_warnings": warnings}

    return extract


def make_plan_case_study_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def plan_node(state: Agent07State) -> dict[str, Any]:
        request = state["request"]
        normalized = state["normalized_context"]
        evidence = state["evidence_map"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": plan_prompt(request, normalized, evidence)},
        ]
        tier = _stage_tier(cfg, "plan_case_study", "cheap")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="plan_case_study",
            tier=tier,
            messages=messages,
            downstream_stages=("draft_case_study",),
            response_schema=CaseStudyPlan,
        )
        candidate = _usable_plan(structured)
        plan = candidate or _plan_fallback(request, normalized, evidence)
        return {
            "plan": plan,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return plan_node


def make_draft_case_study_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def draft_node(state: Agent07State) -> dict[str, Any]:
        request = state["request"]
        normalized = state["normalized_context"]
        evidence = state["evidence_map"]
        plan = state["plan"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": draft_prompt(request, normalized, evidence, plan)},
        ]
        tier = _stage_tier(cfg, "draft_case_study", "strong")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="draft_case_study",
            tier=tier,
            messages=messages,
            response_schema=CaseStudyDraft,
        )
        candidate = _usable_draft(structured, request)
        draft = candidate or _draft_fallback(request, normalized, evidence, plan)
        return {
            "draft": draft,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return draft_node


def make_generate_quotes_ctas_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def quote_node(state: Agent07State) -> dict[str, Any]:
        package = _quote_cta_fallback(state["request"], state["normalized_context"], state["evidence_map"])
        with tel.span("generate_quotes_and_ctas") as span_id:
            tel.log("generate_quotes_and_ctas.complete", span_id=span_id)
        return {"quote_cta_package": package}

    return quote_node


def make_scan_claims_risks_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def risk_node(state: Agent07State) -> dict[str, Any]:
        flags = list(
            build_risk_flags(
                request=state.get("request"),
                draft=state.get("draft"),
                validation_errors=state.get("validation_errors", ()),
            )
        )
        flags.extend(detect_generic_content(request=state.get("request"), draft=state.get("draft")))
        # Preserve order while deduping identical risk records.
        deduped: list[RiskFlag] = []
        seen: set[tuple[str, str, str, str | None]] = set()
        for flag in flags:
            key = (flag.category, flag.severity, flag.message, flag.evidence_needed)
            if key not in seen:
                deduped.append(flag)
                seen.add(key)
        with tel.span("scan_claims_and_risks") as span_id:
            tel.log("scan_claims_and_risks.complete", span_id=span_id, risk_count=len(deduped))
        return {"risk_flags": tuple(deduped)}

    return risk_node


def make_score_quality_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def score_node(state: Agent07State) -> dict[str, Any]:
        quality = score_case_study_quality(
            request=state.get("request"),
            draft=state.get("draft"),
            evidence_map=state.get("evidence_map"),
            missing_warnings=state.get("missing_information_warnings", ()),
            risk_flags=state.get("risk_flags", ()),
            validation_errors=state.get("validation_errors", ()),
        )
        with tel.span("score_quality") as span_id:
            tel.metric("quality.overall_score", quality.overall_score, node="score_quality")
            tel.log("score_quality.complete", span_id=span_id, score=quality.overall_score)
        return {"quality_report": quality}

    return score_node


def make_optional_revision_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def revise_node(state: Agent07State) -> dict[str, Any]:
        quality = state.get("quality_report")
        hard_fail = any(flag.severity == "hard_fail" for flag in state.get("risk_flags", ()))
        attempted = False
        if quality and 65 <= quality.overall_score < 80 and not hard_fail:
            attempted = True
            _safe_log(tel, "optional_revision_pass.applied", score=quality.overall_score)
        with tel.span("optional_revision_pass") as span_id:
            tel.log("optional_revision_pass.complete", span_id=span_id, attempted=attempted)
        return {"revision_attempted": attempted}

    return revise_node


def make_assemble_package_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm

    def assemble(state: Agent07State) -> dict[str, Any]:
        request = state.get("request")
        ceiling = _cost_ceiling(cfg, request)
        stage_costs = list(state.get("cost_usage", []))
        total = round(total_cost_inr(stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total, cost_ceiling_inr=ceiling)
        warnings = state.get("missing_information_warnings", ())
        risks = state.get("risk_flags", ())
        quality = state.get("quality_report") or _zero_quality(state.get("notes", "No quality score available."))
        status = _determine_package_status(state, quality, total=total, ceiling_inr=ceiling)
        pass_status = "pass" if quality.passed and not any(flag.severity == "hard_fail" for flag in risks) else "fail"
        plan = state.get("plan")
        draft = state.get("draft")
        quotes = state.get("quote_cta_package") or QuoteCtaPackage()
        evidence = state.get("evidence_map") or EvidenceMap()
        package = CaseStudyPackage(
            request_id=state.get("request_id", uuid4().hex),
            status=status,  # type: ignore[arg-type]
            pass_status=pass_status,
            recommended_title=plan.recommended_title if plan else None,
            title_options=plan.title_options if plan else (),
            executive_summary=draft.executive_summary if draft else None,
            customer_background=draft.customer_background if draft else None,
            challenge_section=draft.challenge_section if draft else None,
            solution_section=draft.solution_section if draft else None,
            implementation_section=draft.implementation_section if draft else None,
            results_section=draft.results_section if draft else None,
            metric_highlights=evidence.metric_highlights,
            pull_quotes=quotes.pull_quotes,
            customer_quote_placeholders=quotes.customer_quote_placeholders,
            cta_suggestions=quotes.cta_suggestions,
            final_markdown_draft=draft.final_markdown_draft if draft else None,
            missing_information_warnings=warnings,
            risk_flags=risks,
            quality_report=quality,
            cost_usage=cost,
            notes=_determine_notes(state, status),
            improvement_suggestions=_improvement_suggestions(state, status),
            generation_used_llm=bool(state.get("generation_used_llm", False)),
        )
        with tel.span("assemble_package") as span_id:
            tel.metric("total.cost_inr", total, node="assemble_package")
            tel.log("assemble_package.complete", span_id=span_id, status=status)
        return {"status": status, "cost": cost, "final_output": package}

    return assemble


def _zero_quality(reason: str) -> QualityReport:
    dimensions = (
        QualityDimensionScore(name="challenge_clarity", score=0, max_score=15),
        QualityDimensionScore(name="solution_specificity", score=0, max_score=15),
        QualityDimensionScore(name="evidence_backed_results", score=0, max_score=20),
        QualityDimensionScore(name="credibility_claim_safety", score=0, max_score=15),
        QualityDimensionScore(name="structure_completeness", score=0, max_score=10),
        QualityDimensionScore(name="brand_tone_fit", score=0, max_score=10),
        QualityDimensionScore(name="readability", score=0, max_score=10),
        QualityDimensionScore(name="cta_usefulness", score=0, max_score=5),
    )
    return QualityReport(
        overall_score=0,
        dimension_scores=dimensions,
        approval_reason=reason,
        revision_notes=(reason,),
        passed=False,
    )


def _determine_package_status(
    state: Agent07State,
    quality: QualityReport,
    *,
    total: float,
    ceiling_inr: float,
) -> Agent07Status:
    if state.get("error_state") is not None or state.get("validation_errors"):
        return "reject"
    if not state.get("cost_gate_ok", True) or total > ceiling_inr:
        return "reject"
    return determine_status(
        quality=quality,
        risk_flags=state.get("risk_flags", ()),
        missing_warnings=state.get("missing_information_warnings", ()),
        budget_limited=bool(state.get("budget_limited")),
    )  # type: ignore[return-value]


def _determine_notes(state: Agent07State, status: str) -> str:
    if state.get("error_state") is not None:
        error = state.get("error_state", {})
        return f"Error in {error.get('node', 'unknown')} ({error.get('kind', 'Error')})"
    if state.get("validation_errors"):
        return state.get("notes", "Case study request needs required fields.")
    if state.get("budget_limited"):
        return (
            "Budget limit reached before one or more LLM stages; deterministic fallbacks were used. "
            "Review evidence and rerun with a higher configured budget if richer live drafting is needed."
        )
    if status == "approve":
        return "Review-ready case study package generated. Human approval is still required before publication."
    if status == "revise":
        return "Usable case study draft generated, but missing evidence or risk flags require revision."
    return "Case study package is not safe to use without more information or claim review."


def _improvement_suggestions(state: Agent07State, status: str) -> tuple[str, ...]:
    suggestions: list[str] = []
    if state.get("validation_errors"):
        suggestions.extend(state.get("validation_errors", ()))
    for warning in state.get("missing_information_warnings", ()):
        suggestions.append(warning.message)
    for flag in state.get("risk_flags", ()):
        suggestions.append(flag.evidence_needed or flag.message)
    quality = state.get("quality_report")
    if quality:
        suggestions.extend(quality.revision_notes)
    if status != "approve":
        suggestions.append("Have a human verify customer approval, metrics, quotes, and confidentiality before public use.")
    return tuple(dict.fromkeys(item for item in suggestions if item))


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 07's cloud-neutral LangGraph workflow."""
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 25.0))
    nodes = {
        "intake_request": _node_with_error_guard(
            "intake_request", make_intake_request_node(cfg, llm, tel), tel=tel
        ),
        "normalize_input": _node_with_error_guard(
            "normalize_input", make_normalize_input_node(cfg, llm, tel), tel=tel
        ),
        "extract_evidence_and_metrics": _node_with_error_guard(
            "extract_evidence_and_metrics", make_extract_evidence_node(cfg, llm, tel), tel=tel
        ),
        "plan_case_study": _node_with_error_guard(
            "plan_case_study", make_plan_case_study_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "draft_case_study": _node_with_error_guard(
            "draft_case_study", make_draft_case_study_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "generate_quotes_and_ctas": _node_with_error_guard(
            "generate_quotes_and_ctas", make_generate_quotes_ctas_node(cfg, llm, tel), tel=tel
        ),
        "scan_claims_and_risks": _node_with_error_guard(
            "scan_claims_and_risks", make_scan_claims_risks_node(cfg, llm, tel), tel=tel
        ),
        "score_quality": _node_with_error_guard(
            "score_quality", make_score_quality_node(cfg, llm, tel), tel=tel
        ),
        "optional_revision_pass": _node_with_error_guard(
            "optional_revision_pass", make_optional_revision_node(cfg, llm, tel), tel=tel
        ),
        "assemble_package": _safe_assemble_wrapper(make_assemble_package_node(cfg, llm, tel)),
    }

    def _emit_route(node: str, decision: str, target: str) -> None:
        _safe_log(tel, "route.decision", node=node, decision=decision, target=target)

    def route_basic(node: str, target: str):
        def route(state: Agent07State) -> str:
            if state.get("error_state") is not None:
                _emit_route(node, "error", "assemble_package")
                return "assemble_package"
            if not state.get("cost_gate_ok", True):
                _emit_route(node, "cost_ceiling", "assemble_package")
                return "assemble_package"
            _emit_route(node, "ok", target)
            return target

        return route

    def route_after_intake(state: Agent07State) -> str:
        if state.get("error_state") is not None:
            _emit_route("intake_request", "error", "assemble_package")
            return "assemble_package"
        if state.get("validation_errors"):
            _emit_route("intake_request", "reject", "assemble_package")
            return "assemble_package"
        _emit_route("intake_request", "ok", "normalize_input")
        return "normalize_input"

    graph = StateGraph(Agent07State)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.set_entry_point("intake_request")
    graph.add_conditional_edges(
        "intake_request",
        route_after_intake,
        {"normalize_input": "normalize_input", "assemble_package": "assemble_package"},
    )
    edges = (
        ("normalize_input", "extract_evidence_and_metrics"),
        ("extract_evidence_and_metrics", "plan_case_study"),
        ("plan_case_study", "draft_case_study"),
        ("draft_case_study", "generate_quotes_and_ctas"),
        ("generate_quotes_and_ctas", "scan_claims_and_risks"),
        ("scan_claims_and_risks", "score_quality"),
        ("score_quality", "optional_revision_pass"),
        ("optional_revision_pass", "assemble_package"),
    )
    for source, target in edges:
        graph.add_conditional_edges(
            source,
            route_basic(source, target),
            {target: target, "assemble_package": "assemble_package"},
        )
    graph.add_edge("assemble_package", END)
    return graph.compile()


__all__ = [
    "build_graph",
    "_draft_fallback",
    "_normalize_fallback",
    "_plan_fallback",
]
