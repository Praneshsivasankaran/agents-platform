"""Shared LangGraph workflow for Digital Marketing Agents 15-21."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from core.cost import CostCeilingExceeded, estimate_for_stage, estimate_prompt_tokens, resolve_is_mock, total_cost_inr, usage_cost_inr
from core.interfaces import BillableProviderError, LLMResponse, Telemetry
from core.interfaces.llm import LLMProvider

from .profiles import AgentProfile
from .prompts import build_generation_prompt, build_system_prompt
from .schemas import (
    CostUsage,
    DigitalMarketingLLMOutput,
    DigitalMarketingPackage,
    DigitalMarketingRequest,
    QualityDimensionScore,
    QualityReport,
    StageCost,
)
from .scoring import determine_quality_status, determine_terminal_status, score_quality
from .state import DigitalMarketingState
from .tools import (
    build_assumptions,
    build_evidence,
    build_handoffs,
    build_metric_insights,
    build_output_sections,
    build_recommendations,
    detect_risks,
    missing_required_fields,
    new_request_id,
)


class BillableNodeError(Exception):
    """A node failed after a billable provider call and must preserve cost."""

    def __init__(self, stage_cost: StageCost, cause: Exception) -> None:
        self.stage_cost = stage_cost
        self.cause = cause
        super().__init__(f"BillableNodeError wrapping {type(cause).__name__}")


def _safe_log(tel: Telemetry, event: str, **kwargs: Any) -> None:
    try:
        tel.log(event, **kwargs)
    except Exception:
        pass


def _safe_metric(tel: Telemetry, name: str, value: float, **kwargs: Any) -> None:
    try:
        tel.metric(name, value, **kwargs)
    except Exception:
        pass


def _with_span(tel: Telemetry, name: str, event: str, **kwargs: Any) -> None:
    try:
        with tel.span(name) as span_id:
            tel.log(event, span_id=span_id, **kwargs)
    except Exception:
        pass


def _node_with_error_guard(node_name: str, node_fn: Callable, tel: Telemetry) -> Callable:
    def guarded(state: DigitalMarketingState) -> dict[str, Any]:
        try:
            return node_fn(state)
        except BillableNodeError as be:
            _safe_log(tel, "node.error", node=node_name, kind=type(be.cause).__name__)
            return {
                "cost_usage": [be.stage_cost],
                "error_state": {"node": node_name, "kind": type(be.cause).__name__},
            }
        except Exception as exc:  # noqa: BLE001
            _safe_log(tel, "node.error", node=node_name, kind=type(exc).__name__)
            return {"error_state": {"node": node_name, "kind": type(exc).__name__}}

    guarded.__name__ = f"guarded_{node_name}"
    return guarded


def _cost_ceiling(profile: AgentProfile, cfg: dict, request: DigitalMarketingRequest | None = None) -> float:
    configured = float(cfg.get("cost", {}).get("ceiling_inr", profile.cost_ceiling_inr))
    if request is not None and request.max_cost_rs is not None:
        return min(configured, float(request.max_cost_rs))
    return configured


def _stage_tier(profile: AgentProfile, cfg: dict) -> str:
    tier = cfg.get("llm", {}).get("stage_tiers", {}).get(profile.billable_stage, profile.llm_tier)
    if tier not in {"cheap", "strong"}:
        raise ValueError(f"llm.stage_tiers[{profile.billable_stage!r}] must be cheap or strong")
    return tier


def _stage_pricing(cfg: dict, tier: str, stage_name: str) -> tuple[float, float, float, int, int]:
    cost_cfg = cfg.get("cost", {})
    output_cpt = float(cost_cfg.get("output_cost_per_token_inr", {}).get(tier, 0.0))
    input_cpt = float(cost_cfg.get("input_cost_per_token_inr", {}).get(tier, 0.0))
    fixed = float(cost_cfg.get("fixed_cost_inr", {}).get(tier, 0.0))
    max_prompt = int(cost_cfg.get("max_prompt_tokens", {}).get(tier, 32768))
    max_output = int(cost_cfg.get("max_output_tokens", {}).get(stage_name, 4096))
    return output_cpt, input_cpt, fixed, max_prompt, max_output


def _billable_llm_call(
    *,
    profile: AgentProfile,
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    state: DigitalMarketingState,
    messages: list[dict],
) -> tuple[LLMResponse, StageCost]:
    tier = _stage_tier(profile, cfg)
    cost_cfg = cfg.get("cost", {})
    ceiling = _cost_ceiling(profile, cfg, state.get("request"))
    fx_rates = cost_cfg.get("fx_rates", {"USD": 83.0})
    estimated_costs = {k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()}
    output_cpt, input_cpt, fixed, max_prompt, max_output = _stage_pricing(cfg, tier, profile.billable_stage)
    prompt_tokens_est = estimate_prompt_tokens(messages, DigitalMarketingLLMOutput)
    if prompt_tokens_est > max_prompt:
        raise CostCeilingExceeded("prompt estimate exceeds configured max_prompt_tokens")

    current_spend = total_cost_inr(state.get("cost_usage", []))
    stage_reserve = estimate_for_stage(profile.billable_stage, estimated_costs)
    worst_case_inr = (prompt_tokens_est * input_cpt) + (max_output * output_cpt) + fixed
    if not resolve_is_mock(cfg) and current_spend + max(stage_reserve, worst_case_inr) > ceiling:
        raise CostCeilingExceeded(f"{profile.billable_stage}: estimated cost exceeds ceiling")
    if resolve_is_mock(cfg) and current_spend + stage_reserve > ceiling:
        raise CostCeilingExceeded(f"{profile.billable_stage}: mock reserve exceeds ceiling")

    params: dict[str, Any] = {"_authorized_prompt_tokens": prompt_tokens_est}
    if max_output > 0:
        params["max_tokens"] = max_output

    try:
        with tel.span(profile.billable_stage) as span_id:
            try:
                response = llm.respond(
                    messages,
                    tier=tier,  # type: ignore[arg-type]
                    params=params,
                    response_schema=DigitalMarketingLLMOutput,
                )
            except BillableProviderError as bpe:
                stage_cost = StageCost(
                    stage=profile.billable_stage,
                    cost_inr=usage_cost_inr(bpe.usage, fx_rates=fx_rates),
                    tier=tier,  # type: ignore[arg-type]
                    tokens_prompt=bpe.usage.prompt_tokens,
                    tokens_completion=bpe.usage.completion_tokens,
                )
                raise BillableNodeError(stage_cost, RuntimeError(f"billable-provider-failure:{bpe.category}")) from None
            stage_cost = StageCost(
                stage=profile.billable_stage,
                cost_inr=usage_cost_inr(response.usage, fx_rates=fx_rates),
                tier=tier,  # type: ignore[arg-type]
                tokens_prompt=response.usage.prompt_tokens,
                tokens_completion=response.usage.completion_tokens,
            )
            try:
                tel.record_usage(response.usage, node=profile.billable_stage, tier=tier, span_id=span_id)
                tel.metric("stage.cost_inr", stage_cost.cost_inr, node=profile.billable_stage)
                tel.log(f"{profile.billable_stage}.complete", span_id=span_id)
            except Exception as exc:
                raise BillableNodeError(stage_cost, exc) from exc
            return response, stage_cost
    except BillableNodeError:
        raise
    except Exception as exc:
        if "stage_cost" in locals():
            raise BillableNodeError(stage_cost, exc) from exc
        raise


def _usable_llm_output(candidate: object) -> DigitalMarketingLLMOutput | None:
    if not isinstance(candidate, DigitalMarketingLLMOutput):
        return None
    if candidate.summary.lower().strip("x ") == "":
        return None
    if len(candidate.summary.split()) < 8:
        return None
    if not candidate.recommendations:
        return None
    if all(rec.title.lower().strip("x ") == "" for rec in candidate.recommendations):
        return None
    return candidate


def make_intake_node(profile: AgentProfile, cfg: dict, request_cls: type[DigitalMarketingRequest], tel: Telemetry):
    _ = cfg

    def intake(state: DigitalMarketingState) -> dict[str, Any]:
        request_id = state.get("request_id") or new_request_id(profile.agent_id)
        raw = state.get("raw_input", {})
        try:
            request = raw if isinstance(raw, request_cls) else request_cls.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            message = _safe_validation_message(exc)
            _with_span(tel, "intake_request", "intake_request.invalid")
            return {
                "request_id": request_id,
                "validation_errors": (message,),
                "status": "needs_human",
                "cost_ceiling_inr": _cost_ceiling(profile, cfg),
            }
        missing = missing_required_fields(profile, request)
        _with_span(tel, "intake_request", "intake_request.accepted", missing_count=len(missing))
        return {
            "request_id": request_id,
            "request": request,
            "validation_errors": (),
            "status": "running",
            "cost_ceiling_inr": _cost_ceiling(profile, cfg, request),
        }

    return intake


def _safe_validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        fields = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "input"
            fields.append(loc)
        return "Missing or invalid Digital Marketing fields: " + ", ".join(dict.fromkeys(fields))
    return "Invalid Digital Marketing input: " + type(exc).__name__


def make_analyze_context_node(profile: AgentProfile, cfg: dict, tel: Telemetry):
    _ = cfg

    def analyze(state: DigitalMarketingState) -> dict[str, Any]:
        request = state.get("request")
        risks = detect_risks(profile, request)
        evidence = build_evidence(request)
        metric_insights = build_metric_insights(profile, request)
        assumptions = build_assumptions(profile, request)
        _with_span(
            tel,
            "analyze_context",
            "analyze_context.complete",
            risk_count=len(risks),
            evidence_count=len(evidence),
        )
        return {
            "risk_flags": risks,
            "evidence": evidence,
            "metric_insights": metric_insights,
            "assumptions": assumptions,
        }

    return analyze


def make_generate_node(profile: AgentProfile, cfg: dict, llm: LLMProvider, tel: Telemetry):
    def generate(state: DigitalMarketingState) -> dict[str, Any]:
        request = state.get("request")
        risks = state.get("risk_flags", ())
        evidence = state.get("evidence", ())
        metric_insights = state.get("metric_insights", ())
        output_sections = build_output_sections(profile, request, evidence, risks)
        if request is None or any(flag.severity == "hard_fail" for flag in risks):
            recommendations = build_recommendations(profile, request, evidence, risks, metric_insights)
            return {"recommendations": recommendations, "output_sections": output_sections, "generation_used_llm": False}
        messages = [
            {"role": "system", "content": build_system_prompt(profile)},
            {"role": "user", "content": build_generation_prompt(profile, request)},
        ]
        try:
            response, stage_cost = _billable_llm_call(
                profile=profile,
                cfg=cfg,
                llm=llm,
                tel=tel,
                state=state,
                messages=messages,
            )
            candidate = _usable_llm_output(response.structured)
            if candidate is not None:
                return {
                    "recommendations": candidate.recommendations,
                    "output_sections": output_sections,
                    "assumptions": tuple(dict.fromkeys(state.get("assumptions", ()) + candidate.assumptions)),
                    "cost_usage": [stage_cost],
                    "generation_used_llm": True,
                }
            recommendations = build_recommendations(profile, request, evidence, risks, metric_insights)
            return {
                "recommendations": recommendations,
                "output_sections": output_sections,
                "cost_usage": [stage_cost],
                "generation_used_llm": False,
            }
        except CostCeilingExceeded:
            recommendations = build_recommendations(profile, request, evidence, risks, metric_insights)
            _safe_log(tel, f"{profile.billable_stage}.provider_hiccup", node=profile.billable_stage, kind="cost_ceiling")
            return {
                "recommendations": recommendations,
                "output_sections": output_sections,
                "budget_limited": True,
                "generation_used_llm": False,
            }
        except BillableNodeError:
            raise
        except Exception as exc:  # noqa: BLE001
            recommendations = build_recommendations(profile, request, evidence, risks, metric_insights)
            _safe_log(tel, f"{profile.billable_stage}.provider_hiccup", node=profile.billable_stage, kind=type(exc).__name__)
            return {"recommendations": recommendations, "output_sections": output_sections, "generation_used_llm": False}

    return generate


def make_score_node(profile: AgentProfile, cfg: dict, tel: Telemetry):
    _ = cfg

    def score(state: DigitalMarketingState) -> dict[str, Any]:
        quality = score_quality(
            profile=profile,
            request=state.get("request"),
            recommendations=state.get("recommendations", ()),
            output_sections=state.get("output_sections", ()),
            risks=state.get("risk_flags", ()),
            metric_insights=state.get("metric_insights", ()),
            validation_errors=state.get("validation_errors", ()),
        )
        _safe_metric(tel, "quality.overall_score", quality.overall_score, node="score_quality")
        _with_span(tel, "score_quality", "score_quality.complete", score=quality.overall_score)
        return {"quality_report": quality}

    return score


def make_assemble_node(profile: AgentProfile, cfg: dict, package_cls: type[DigitalMarketingPackage], tel: Telemetry):
    def assemble(state: DigitalMarketingState) -> dict[str, Any]:
        request = state.get("request")
        risks = state.get("risk_flags", ())
        stage_costs = list(state.get("cost_usage", []))
        ceiling = _cost_ceiling(profile, cfg, request)
        total = round(total_cost_inr(stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total, cost_ceiling_inr=ceiling)
        quality = state.get("quality_report") or _zero_quality(profile, state.get("validation_errors", ()))
        quality_status = determine_quality_status(profile, quality, risks)
        terminal = determine_terminal_status(
            quality_status=quality_status,
            quality=quality,
            risks=risks,
            budget_limited=bool(state.get("budget_limited")),
            error=bool(state.get("error_state")),
        )
        pass_status = "pass" if quality.passed and not any(flag.severity == "hard_fail" for flag in risks) else "fail"
        data_quality = tuple(
            flag
            for flag in risks
            if flag.category in {"data_quality", "metric_fabrication", "unsupported_claim", "misrepresentation"}
        )
        package = package_cls(
            request_id=state.get("request_id", new_request_id(profile.agent_id)),
            agent_id=profile.agent_id,
            agent_name=profile.title,
            status=terminal,  # type: ignore[arg-type]
            terminal_status=terminal,  # type: ignore[arg-type]
            quality_status=quality_status,  # type: ignore[arg-type]
            pass_status=pass_status,
            summary=_summary(profile, terminal, state),
            output_sections=state.get("output_sections", ()),
            primary_recommendations=state.get("recommendations", ()),
            evidence=state.get("evidence", ()),
            assumptions=state.get("assumptions", ()),
            metric_insights=state.get("metric_insights", ()),
            data_quality_warnings=data_quality,
            handoffs=build_handoffs(profile, request),
            risk_flags=risks,
            quality_report=quality,
            cost_usage=cost,
            notes=_notes(profile, terminal, state),
            generation_used_llm=bool(state.get("generation_used_llm", False)),
        )
        _safe_metric(tel, "total.cost_inr", total, node="assemble_package")
        _with_span(tel, "assemble_package", "assemble_package.complete", status=terminal)
        return {"final_output": package, "status": terminal, "cost": cost}

    return assemble


def _zero_quality(profile: AgentProfile, validation_errors: tuple[str, ...]) -> QualityReport:
    dimensions = tuple(
        QualityDimensionScore(name=name, score=0, max_score=max_score)
        for name, max_score in profile.quality_dimensions
    )
    return QualityReport(
        overall_score=0,
        dimension_scores=dimensions,
        approval_reason="Required inputs are missing or invalid.",
        revision_notes=validation_errors,
        passed=False,
    )


def _summary(profile: AgentProfile, terminal: str, state: DigitalMarketingState) -> str:
    if terminal == "pass":
        return f"{profile.title} produced a review-ready {profile.primary_object}."
    if terminal == "stopped_cost_ceiling":
        return f"{profile.title} returned deterministic advisory guidance after the cost ceiling blocked model generation."
    if terminal == "error":
        return f"{profile.title} hit an error and returned a safe structured response."
    if any(flag.severity == "hard_fail" for flag in state.get("risk_flags", ())):
        return f"{profile.title} found a hard-fail v1 scope, safety, data, or truthfulness issue requiring human review."
    return f"{profile.title} produced advisory output that needs human review before use."


def _notes(profile: AgentProfile, terminal: str, state: DigitalMarketingState) -> str:
    if terminal == "stopped_cost_ceiling":
        return "Cost ceiling reached before the billable generation stage; deterministic fallback output was returned."
    if terminal == "error":
        error = state.get("error_state", {})
        return f"Error in {error.get('node', 'unknown')} ({error.get('kind', 'Error')})."
    if state.get("validation_errors"):
        return "; ".join(state.get("validation_errors", ()))
    if any(flag.severity == "hard_fail" for flag in state.get("risk_flags", ())):
        return "Hard-fail risks require human correction or future integration design before action."
    return f"Human review is required before operational use of this {profile.primary_object}."


def build_graph(
    profile: AgentProfile,
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    *,
    request_cls: type[DigitalMarketingRequest] = DigitalMarketingRequest,
    package_cls: type[DigitalMarketingPackage] = DigitalMarketingPackage,
) -> Any:
    """Compile a cloud-neutral Digital Marketing LangGraph workflow."""
    generation_node = profile.billable_stage
    nodes = {
        "intake_request": _node_with_error_guard("intake_request", make_intake_node(profile, cfg, request_cls, tel), tel),
        "analyze_context": _node_with_error_guard("analyze_context", make_analyze_context_node(profile, cfg, tel), tel),
        generation_node: _node_with_error_guard(generation_node, make_generate_node(profile, cfg, llm, tel), tel),
        "score_quality": _node_with_error_guard("score_quality", make_score_node(profile, cfg, tel), tel),
        "assemble_package": make_assemble_node(profile, cfg, package_cls, tel),
    }

    def route_after_intake(state: DigitalMarketingState) -> str:
        if state.get("validation_errors"):
            _safe_log(tel, "route.decision", node="intake_request", decision="invalid", target="score_quality")
            return "score_quality"
        _safe_log(tel, "route.decision", node="intake_request", decision="ok", target="analyze_context")
        return "analyze_context"

    def route_basic(node: str, target: str):
        def route(state: DigitalMarketingState) -> str:
            if state.get("error_state") is not None:
                _safe_log(tel, "route.decision", node=node, decision="error", target="assemble_package")
                return "assemble_package"
            _safe_log(tel, "route.decision", node=node, decision="ok", target=target)
            return target

        return route

    graph = StateGraph(DigitalMarketingState)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.set_entry_point("intake_request")
    graph.add_conditional_edges(
        "intake_request",
        route_after_intake,
        {"analyze_context": "analyze_context", "score_quality": "score_quality"},
    )
    graph.add_conditional_edges(
        "analyze_context",
        route_basic("analyze_context", generation_node),
        {generation_node: generation_node, "assemble_package": "assemble_package"},
    )
    graph.add_conditional_edges(
        generation_node,
        route_basic(generation_node, "score_quality"),
        {"score_quality": "score_quality", "assemble_package": "assemble_package"},
    )
    graph.add_conditional_edges(
        "score_quality",
        route_basic("score_quality", "assemble_package"),
        {"assemble_package": "assemble_package"},
    )
    graph.add_edge("assemble_package", END)
    return graph.compile()
