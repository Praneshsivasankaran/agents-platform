"""LangGraph workflow for Agent 05 - Editorial Planning Agent."""
from __future__ import annotations

import json
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
    build_system,
    content_briefs_prompt,
    platform_strategy_prompt,
    repurposing_prompt,
    topic_plan_prompt,
)
from .schemas import (
    Agent05Request,
    BalanceGapAnalysis,
    BillableNodeError,
    ContentBrief,
    ContentBriefPackage,
    CostUsage,
    CountItem,
    CTARecommendation,
    EditorialCalendarItem,
    EditorialPlanningPackage,
    PeriodPlan,
    PlatformPlan,
    PlatformPlanSummary,
    PlatformStrategyPackage,
    RepurposingMapItem,
    RepurposingMapPackage,
    StageCost,
    TopicPlanItem,
    TopicPlanPackage,
)
from .scoring import build_risk_report, score_output
from .state import Agent05State
from .tools import (
    calculate_internal_due_date,
    clean_text,
    count_by,
    expand_posting_frequency,
    month_label,
    normalize_platforms,
    parse_date,
    planned_post_count,
    split_text_items,
    validate_date_range,
    week_label,
)


_ALIASES = {
    "brand": "brand_name",
    "company": "brand_name",
    "company_name": "brand_name",
    "goal": "business_goal",
    "audience": "target_audience",
    "theme": "campaign_theme",
    "tone": "brand_voice",
    "voice": "brand_voice",
    "pillars": "content_pillars",
    "themes": "content_pillars",
    "ideas": "existing_ideas",
    "start_date": "date_range.start",
    "end_date": "date_range.end",
    "frequency": "posting_frequency.cadence",
}

_BILLABLE_STAGES = (
    "map_platform_strategy",
    "generate_topic_plan",
    "generate_content_briefs",
    "build_repurposing_map",
)


def _node_with_error_guard(
    node_name: str,
    node_fn: Callable,
    *,
    ceiling_inr: float = math.inf,
    tel: Telemetry | None = None,
) -> Callable:
    """Wrap a graph node so every failure reaches assemble with structured status."""

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
            pkg = EditorialPlanningPackage(
                status="error",
                cost=cost,
                notes=f"Fatal error in assemble_package ({type(exc).__name__})",
            )
            return {"final_output": pkg, "status": "error"}

    safe_assemble.__name__ = "safe_assemble_package"
    return safe_assemble


def _apply_dotted_alias(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    first, second = dotted_key.split(".", 1)
    nested = data.get(first)
    if not isinstance(nested, dict):
        nested = {}
        data[first] = nested
    nested.setdefault(second, value)


def _request_from_state(state: Agent05State) -> Agent05Request:
    existing = state.get("request")
    if isinstance(existing, Agent05Request):
        return existing
    raw = state.get("raw_input")
    if isinstance(raw, Agent05Request):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("Agent 05 input must be a serialized editorial planning request")
    data = dict(raw)
    for old_key, new_key in _ALIASES.items():
        if old_key not in data:
            continue
        if "." in new_key:
            _apply_dotted_alias(data, new_key, data[old_key])
        else:
            data.setdefault(new_key, data[old_key])
    if "date_range" not in data:
        data["date_range"] = {
            "start": data.get("start") or data.get("start_date") or "",
            "end": data.get("end") or data.get("end_date") or "",
        }
    if "posting_frequency" not in data:
        data["posting_frequency"] = {}
    if isinstance(data["posting_frequency"], str):
        data["posting_frequency"] = {"cadence": data["posting_frequency"]}
    for key in (
        "platforms",
        "content_pillars",
        "existing_ideas",
        "constraints",
        "priority_platforms",
        "excluded_topics",
        "key_products",
        "important_dates",
        "regional_preferences",
    ):
        if key in data:
            data[key] = split_text_items(data[key])
    if "platforms" in data:
        data["platforms"] = normalize_platforms(data["platforms"])
    return Agent05Request.model_validate(data)


def _safe_validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        fields = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "input"
            fields.append(loc)
        return "Missing or invalid editorial planning fields: " + ", ".join(dict.fromkeys(fields))
    return "Invalid Agent 05 input: " + type(exc).__name__


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
    state: Agent05State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[LLMResponse, StageCost]:
    cost_cfg = cfg.get("cost", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr = float(cost_cfg.get("ceiling_inr", 30.0))
    estimated_costs = {k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()}
    is_mock = resolve_is_mock(cfg)
    output_cpt, input_cpt, fixed, max_prompt, tier_max_output = _stage_pricing(cfg, tier)
    max_output = int(cost_cfg.get("max_output_tokens", {}).get(stage_name, tier_max_output))
    prompt_tokens_est = estimate_prompt_tokens(messages, response_schema)
    if prompt_tokens_est > max_prompt:
        raise CostCeilingExceeded(
            f"{stage_name}: prompt estimate {prompt_tokens_est} exceeds max_prompt_tokens={max_prompt}"
        )

    # Strong pre-call worst-case gate (live mode): the most this call can possibly cost is
    # prompt_tokens * input + (strict output cap) * output + fixed. Block BEFORE the provider
    # is called if running it — plus the reserve for mandatory downstream stages — could push
    # the run over the ceiling. Because the call is then capped at `max_output` tokens, the
    # actual cost can never exceed this worst case, so the total stays under ceiling_inr.
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
    # Always cap output by the strict per-stage config limit so the call cannot exceed the
    # worst case we just budgeted for (auth.max_tokens may be larger when there is headroom).
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
    state: Agent05State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[object | None, list[StageCost], bool, bool]:
    """Run a billable stage, degrading gracefully.

    Returns ``(structured, stage_costs, used, blocked)``:
    - ``used`` is True when the provider returned output that the caller can try to use.
    - ``blocked`` is True when the pre-call budget gate refused to start the stage. The caller
      then uses its deterministic fallback and the run is marked budget-limited — no provider
      call is made and no cost is incurred, so the ceiling is never breached.
    """
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
        # Budget too low to safely run this stage. Skip the call (no spend), fall back, and
        # signal budget-limited so the package is partial-but-useful instead of a hard stop.
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
    return not text or len(text) < 3 or set(text) <= {"x"}


def _platform_strategy_fallback(request: Agent05Request) -> PlatformStrategyPackage:
    plans = []
    for platform in request.platforms:
        if platform == "blog":
            types = ("educational article", "campaign explainer")
        elif platform in {"linkedin", "twitter"}:
            types = ("thought leadership post", "short insight post")
        elif platform in {"email", "newsletter"}:
            types = ("newsletter feature", "nurture email")
        else:
            types = ("platform-native post", "campaign update")
        plans.append(
            PlatformPlan(
                platform=platform,
                role=f"Support {request.business_goal} for {request.target_audience}.",
                recommended_content_types=types,
                cadence_notes="Use this platform for review-ready planned items only; no scheduling is performed.",
                cta_guidance=f"Point readers toward {request.business_goal.lower()} with a human-approved CTA.",
            )
        )
    return PlatformStrategyPackage(
        platform_plans=tuple(plans),
        notes=("Deterministic platform strategy fallback used.",),
    )


def _usable_platform_strategy(candidate: object, request: Agent05Request) -> PlatformStrategyPackage | None:
    if not isinstance(candidate, PlatformStrategyPackage):
        return None
    if not candidate.platform_plans:
        return None
    candidate_platforms = {plan.platform for plan in candidate.platform_plans}
    if not set(request.platforms).issubset(candidate_platforms):
        return None
    if any(_is_generic_text(plan.role) for plan in candidate.platform_plans):
        return None
    return candidate


def _content_type_for(platform: str, sequence: int) -> str:
    options = {
        "blog": ("educational article", "how-to guide", "campaign explainer"),
        "linkedin": ("thought leadership post", "carousel outline", "discussion prompt"),
        "email": ("newsletter feature", "nurture email", "announcement email"),
        "instagram": ("caption brief", "story sequence", "carousel brief"),
        "twitter": ("thread outline", "short post", "discussion prompt"),
    }
    choices = options.get(platform, ("platform-native post", "campaign update", "short brief"))
    return choices[(sequence - 1) % len(choices)]


def _topic_plan_fallback(request: Agent05Request, skeleton: tuple) -> TopicPlanPackage:
    ideas = tuple(request.existing_ideas)
    items: list[TopicPlanItem] = []
    for index, slot in enumerate(skeleton):
        idea = ideas[index % len(ideas)] if ideas else ""
        topic_base = idea or f"{request.campaign_theme} for {request.target_audience}"
        topic = f"{topic_base} - {slot.pillar} angle {slot.sequence}"
        content_type = _content_type_for(slot.platform, slot.sequence)
        priority = "high" if slot.sequence <= max(1, len(skeleton) // 4) else "medium"
        if slot.sequence > max(2, int(len(skeleton) * 0.75)):
            priority = "low"
        items.append(
            TopicPlanItem(
                slot_id=slot.slot_id,
                planned_date=slot.planned_date,
                platform=slot.platform,
                pillar=slot.pillar,
                topic=topic,
                suggested_title=f"{request.campaign_theme}: {slot.pillar.title()} for {request.target_audience}",
                content_type=content_type,
                objective=f"Support {request.business_goal} by addressing {request.target_audience}.",
                primary_cta=f"Invite readers to take the next reviewed step toward {request.business_goal}.",
                priority=priority,  # type: ignore[arg-type]
                rationale="Assigned by cadence, pillar balance, platform rotation, and campaign goal fit.",
            )
        )
    return TopicPlanPackage(items=tuple(items))


def _usable_topic_plan(candidate: object, skeleton: tuple) -> TopicPlanPackage | None:
    if not isinstance(candidate, TopicPlanPackage):
        return None
    if len(candidate.items) < len(skeleton):
        return None
    if any(_is_generic_text(item.topic) or _is_generic_text(item.suggested_title) for item in candidate.items):
        return None
    return candidate


def _content_briefs_fallback(request: Agent05Request, topic_plan: TopicPlanPackage) -> ContentBriefPackage:
    briefs: list[ContentBrief] = []
    for index, item in enumerate(topic_plan.items, start=1):
        brief_id = f"brief-{index:03d}"
        constraints = request.constraints + tuple(f"Exclude: {topic}" for topic in request.excluded_topics)
        briefs.append(
            ContentBrief(
                brief_id=brief_id,
                calendar_item_id=item.slot_id,
                title=item.suggested_title,
                platform=item.platform,
                content_type=item.content_type,
                objective=item.objective,
                audience=request.target_audience,
                key_message=(
                    f"{request.brand_name} should help {request.target_audience} understand "
                    f"{item.topic} in a {request.brand_voice} voice."
                ),
                outline=(
                    f"Open with the {request.target_audience} problem.",
                    f"Explain the {item.pillar} angle in practical terms.",
                    "Add examples only when supplied by the user.",
                    "Close with a human-reviewed CTA.",
                ),
                cta_suggestions=(item.primary_cta,),
                constraints=constraints,
                review_notes=(
                    "Planning brief only; no publication or scheduling action has been taken.",
                    "Verify sensitive claims and examples before content creation.",
                ),
            )
        )
    return ContentBriefPackage(briefs=tuple(briefs))


def _usable_content_briefs(candidate: object, topic_plan: TopicPlanPackage) -> ContentBriefPackage | None:
    if not isinstance(candidate, ContentBriefPackage):
        return None
    if len(candidate.briefs) < len(topic_plan.items):
        return None
    if any(_is_generic_text(brief.key_message) or len(brief.outline) < 2 for brief in candidate.briefs):
        return None
    return candidate


_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _split_for_briefs(
    items: tuple[TopicPlanItem, ...],
    max_full: int,
) -> tuple[tuple[TopicPlanItem, ...], tuple[TopicPlanItem, ...]]:
    """Split planned items into (full-brief items, light-summary items).

    The highest-priority items (then earliest in the calendar) get full briefs; the rest get
    lighter deterministic summaries. When ``max_full`` covers every item, all items are full.
    """
    if max_full <= 0 or len(items) <= max_full:
        return tuple(items), ()
    order = sorted(range(len(items)), key=lambda i: (_PRIORITY_RANK.get(items[i].priority, 1), i))
    full_idx = set(order[:max_full])
    full_items = tuple(item for i, item in enumerate(items) if i in full_idx)
    light_items = tuple(item for i, item in enumerate(items) if i not in full_idx)
    return full_items, light_items


def _light_brief_summaries(
    request: Agent05Request,
    items: tuple[TopicPlanItem, ...],
) -> tuple[ContentBrief, ...]:
    """Concise, non-LLM summary briefs for lower-priority items (kept short to avoid repetition)."""
    constraints = request.constraints + tuple(f"Exclude: {topic}" for topic in request.excluded_topics)
    briefs: list[ContentBrief] = []
    for index, item in enumerate(items, start=1):
        briefs.append(
            ContentBrief(
                brief_id=f"brief-lite-{index:03d}",
                calendar_item_id=item.slot_id,
                title=item.suggested_title,
                platform=item.platform,
                content_type=item.content_type,
                objective=item.objective,
                audience=request.target_audience,
                key_message=(
                    f"Summary brief: cover {item.topic} for {request.target_audience} "
                    f"in a {request.brand_voice} voice."
                ),
                outline=(
                    f"Open on the {item.pillar} angle for {request.target_audience}.",
                    f"Make one concrete point about {item.topic}.",
                    "Close with a human-reviewed CTA.",
                ),
                cta_suggestions=(item.primary_cta,),
                constraints=constraints,
                review_notes=(
                    "Lighter summary brief generated under budget control; expand before production.",
                ),
            )
        )
    return tuple(briefs)


def _order_briefs(
    briefs: tuple[ContentBrief, ...],
    items: tuple[TopicPlanItem, ...],
) -> tuple[ContentBrief, ...]:
    """Return briefs ordered by their item's position in the calendar (stable, by slot)."""
    order = {item.slot_id: i for i, item in enumerate(items)}
    return tuple(sorted(briefs, key=lambda b: order.get(b.calendar_item_id, len(order))))


def _repurposing_fallback(request: Agent05Request, topic_plan: TopicPlanPackage) -> RepurposingMapPackage:
    if len(request.platforms) <= 1:
        return RepurposingMapPackage(items=())
    items: list[RepurposingMapItem] = []
    primary = request.platforms[0]
    for index, topic in enumerate(topic_plan.items[: min(8, len(topic_plan.items))], start=1):
        for target in request.platforms:
            if target == topic.platform:
                continue
            items.append(
                RepurposingMapItem(
                    source_brief_id=f"brief-{topic.sequence if hasattr(topic, 'sequence') else index:03d}",
                    source_platform=topic.platform or primary,
                    target_platform=target,
                    repurposed_format=_content_type_for(target, index),
                    adaptation_note=(
                        f"Adapt the {topic.pillar} message for {target}; keep the CTA and claims "
                        "under human review."
                    ),
                )
            )
            break
    return RepurposingMapPackage(items=tuple(items))


def _usable_repurposing(candidate: object, request: Agent05Request) -> RepurposingMapPackage | None:
    if not isinstance(candidate, RepurposingMapPackage):
        return None
    if len(request.platforms) > 1 and not candidate.items:
        return None
    if any(_is_generic_text(item.adaptation_note) for item in candidate.items):
        return None
    return candidate


def _calendar_items(
    request: Agent05Request,
    topic_plan: TopicPlanPackage | None,
    briefs: ContentBriefPackage | None,
) -> tuple[EditorialCalendarItem, ...]:
    if topic_plan is None:
        return ()
    brief_by_slot = {
        brief.calendar_item_id: brief.brief_id
        for brief in (briefs.briefs if briefs else ())
    }
    out: list[EditorialCalendarItem] = []
    for index, item in enumerate(topic_plan.items, start=1):
        out.append(
            EditorialCalendarItem(
                brief_id=brief_by_slot.get(item.slot_id, f"brief-{index:03d}"),
                planned_date=item.planned_date,
                internal_due_date=calculate_internal_due_date(
                    item.planned_date,
                    request.approval_lead_time_days,
                ),
                platform=item.platform,
                pillar=item.pillar,
                content_type=item.content_type,
                topic=item.topic,
                suggested_title=item.suggested_title,
                objective=item.objective,
                primary_cta=item.primary_cta,
                priority=item.priority,
            )
        )
    return tuple(out)


def _period_plans(
    items: tuple[EditorialCalendarItem, ...],
    *,
    mode: str,
) -> tuple[PeriodPlan, ...]:
    grouped: dict[str, list[EditorialCalendarItem]] = {}
    for item in items:
        label = week_label(item.planned_date) if mode == "week" else month_label(item.planned_date)
        grouped.setdefault(label, []).append(item)
    periods: list[PeriodPlan] = []
    for label, group in sorted(grouped.items()):
        dates = sorted(item.planned_date for item in group)
        platforms = tuple(sorted({item.platform for item in group}))
        focus = group[0].pillar if group else "campaign"
        periods.append(
            PeriodPlan(
                period_label=label,
                start_date=dates[0],
                end_date=dates[-1],
                planned_items=len(group),
                focus=f"{focus.title()} content for {', '.join(platforms)}",
                platforms=platforms,
                notes=("Review workload and approval timing before execution.",),
            )
        )
    return tuple(periods)


def _platform_summaries(items: tuple[EditorialCalendarItem, ...]) -> tuple[PlatformPlanSummary, ...]:
    summaries: list[PlatformPlanSummary] = []
    for platform, count in count_by(tuple(item.platform for item in items)):
        platform_items = tuple(item for item in items if item.platform == platform)
        summaries.append(
            PlatformPlanSummary(
                platform=platform,
                planned_count=count,
                primary_objective=platform_items[0].objective if platform_items else "Support campaign goal.",
                content_types=tuple(sorted({item.content_type for item in platform_items})),
                notes=("Planning only; no platform API call or scheduling action was taken.",),
            )
        )
    return tuple(summaries)


def _balance_analysis(request: Agent05Request, items: tuple[EditorialCalendarItem, ...]) -> BalanceGapAnalysis:
    pillar_counts_raw = dict(count_by(tuple(item.pillar for item in items)))
    platform_counts_raw = dict(count_by(tuple(item.platform for item in items)))
    content_type_counts_raw = dict(count_by(tuple(item.content_type for item in items)))
    pillar_counts = tuple(
        CountItem(name=pillar, count=pillar_counts_raw.get(pillar, 0))
        for pillar in request.content_pillars
    )
    platform_counts = tuple(
        CountItem(name=platform, count=platform_counts_raw.get(platform, 0))
        for platform in request.platforms
    )
    content_type_counts = tuple(CountItem(name=name, count=count) for name, count in sorted(content_type_counts_raw.items()))

    pillar_notes = []
    for item in pillar_counts:
        if item.count == 0:
            pillar_notes.append(f"Missing coverage for pillar: {item.name}.")
    if not pillar_notes:
        pillar_notes.append("All requested pillars have planned coverage.")

    platform_notes = []
    for item in platform_counts:
        if item.count == 0:
            platform_notes.append(f"Missing coverage for platform: {item.name}.")
    if not platform_notes:
        platform_notes.append("All requested platforms have planned coverage.")

    gap_summary = []
    if len(items) < len(request.platforms):
        gap_summary.append("The plan has fewer items than platforms.")
    if not request.existing_ideas:
        gap_summary.append("No existing ideas were supplied; topics are generated from campaign context.")
    if not gap_summary:
        gap_summary.append("No major balance gaps detected in the generated plan.")

    return BalanceGapAnalysis(
        pillar_counts=pillar_counts,
        platform_counts=platform_counts,
        content_type_counts=content_type_counts,
        pillar_balance_notes=tuple(pillar_notes),
        platform_balance_notes=tuple(platform_notes),
        content_type_notes=("Review whether the mix matches production capacity.",),
        gap_summary=tuple(gap_summary),
        recommendations=(
            "Review high-priority items first.",
            "Confirm due dates with the content owner before production.",
            "Treat every item as a draft planning recommendation.",
        ),
    )


def make_intake_validate_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def intake(state: Agent05State) -> dict[str, Any]:
        with tel.span("intake_validate") as span_id:
            try:
                request = _request_from_state(state)
                date_errors = validate_date_range(request.date_range.start, request.date_range.end)
                if date_errors:
                    raise ValueError("; ".join(date_errors))
            except Exception as exc:  # noqa: BLE001
                message = _safe_validation_message(exc)
                tel.log("intake_validate.invalid", span_id=span_id)
                return {
                    "request_id": state.get("request_id") or f"agent05-{uuid4().hex[:12]}",
                    "status": "needs_more_input",
                    "notes": message,
                    "validation_errors": (message,),
                    "cost_usage": [],
                    "cost_gate_ok": True,
                    "generation_used_llm": False,
                }
            tel.log("intake_validate.accepted", span_id=span_id)
            return {
                "request_id": state.get("request_id") or f"agent05-{uuid4().hex[:12]}",
                "request": request,
                "raw_input": request.model_dump(mode="json"),
                "status": "running",
                "validation_errors": (),
                "cost_usage": [],
                "cost_gate_ok": True,
                "generation_used_llm": False,
            }

    return intake


def make_normalize_request_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def normalize(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        normalized = request.model_dump(mode="json")
        with tel.span("normalize_request") as span_id:
            tel.log("normalize_request.complete", span_id=span_id)
        return {"normalized_request": normalized}

    return normalize


def make_validate_date_and_frequency_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def validate_node(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        warnings: list[str] = []
        count = planned_post_count(
            request.date_range.start,
            request.date_range.end,
            request.posting_frequency,
        )
        if count > 120:
            warnings.append("Posting frequency produces more than 120 planned items; review capacity.")
        if request.production_capacity_per_week and count > request.production_capacity_per_week * 8:
            warnings.append("Posting frequency may exceed supplied production capacity.")
        with tel.span("validate_date_and_frequency") as span_id:
            tel.log("validate_date_and_frequency.complete", span_id=span_id)
        return {"validation_errors": tuple(warnings)}

    return validate_node


def make_build_calendar_skeleton_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def build_skeleton(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        skeleton = expand_posting_frequency(
            start=request.date_range.start,
            end=request.date_range.end,
            frequency=request.posting_frequency,
            platforms=request.platforms,
            pillars=request.content_pillars,
        )
        with tel.span("build_calendar_skeleton") as span_id:
            tel.log("build_calendar_skeleton.complete", span_id=span_id, planned_items=len(skeleton))
        return {"calendar_skeleton": skeleton}

    return build_skeleton


def make_map_platform_strategy_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def map_strategy(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        skeleton = state["calendar_skeleton"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {
                "role": "user",
                "content": platform_strategy_prompt(
                    request,
                    json.dumps([slot.model_dump(mode="json") for slot in skeleton], sort_keys=True),
                ),
            },
        ]
        tier = _stage_tier(cfg, "map_platform_strategy", "cheap")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="map_platform_strategy",
            tier=tier,
            messages=messages,
            downstream_stages=("generate_topic_plan", "generate_content_briefs", "build_repurposing_map"),
            response_schema=PlatformStrategyPackage,
        )
        candidate = _usable_platform_strategy(structured, request)
        strategy = candidate or _platform_strategy_fallback(request)
        return {
            "platform_strategy": strategy,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return map_strategy


def make_generate_topic_plan_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def generate_topics(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        skeleton = state["calendar_skeleton"]
        strategy = state["platform_strategy"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {
                "role": "user",
                "content": topic_plan_prompt(
                    request,
                    strategy.model_dump_json(),
                    json.dumps([slot.model_dump(mode="json") for slot in skeleton], sort_keys=True),
                ),
            },
        ]
        tier = _stage_tier(cfg, "generate_topic_plan", "strong")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="generate_topic_plan",
            tier=tier,
            messages=messages,
            downstream_stages=("generate_content_briefs", "build_repurposing_map"),
            response_schema=TopicPlanPackage,
        )
        candidate = _usable_topic_plan(structured, skeleton)
        topic_plan = candidate or _topic_plan_fallback(request, skeleton)
        return {
            "topic_plan": topic_plan,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return generate_topics


def make_generate_content_briefs_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    max_full = int(cfg.get("llm", {}).get("max_full_briefs_live_mode", 5))

    def generate_briefs(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        topic_plan = state["topic_plan"]
        items = topic_plan.items
        # Cost control: ask the model for full briefs only on the highest-priority items.
        # The rest get lighter deterministic summary briefs. This bounds the (expensive)
        # briefs call regardless of how large the calendar is.
        full_items, light_items = _split_for_briefs(items, max_full)
        full_plan = TopicPlanPackage(items=full_items) if full_items else None

        stage_costs: list[StageCost] = []
        used = False
        blocked = False
        candidate: ContentBriefPackage | None = None
        full_briefs: tuple[ContentBrief, ...] = ()

        if full_plan is not None:
            messages = [
                {"role": "system", "content": build_system(cfg)},
                {"role": "user", "content": content_briefs_prompt(request, full_plan.model_dump_json())},
            ]
            tier = _stage_tier(cfg, "generate_content_briefs", "strong")
            structured, stage_costs, used, blocked = _best_effort_llm_call(
                cfg=cfg,
                llm=llm,
                tel=tel,
                state=state,
                stage_name="generate_content_briefs",
                tier=tier,
                messages=messages,
                downstream_stages=("build_repurposing_map",),
                response_schema=ContentBriefPackage,
            )
            candidate = _usable_content_briefs(structured, full_plan)
            full_briefs = (candidate or _content_briefs_fallback(request, full_plan)).briefs

        light_briefs = _light_brief_summaries(request, light_items)
        combined = _order_briefs(full_briefs + light_briefs, items)
        briefs = ContentBriefPackage(briefs=combined) if combined else _content_briefs_fallback(request, topic_plan)
        return {
            "content_briefs": briefs,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return generate_briefs


def make_build_repurposing_map_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def build_map(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        topic_plan = state["topic_plan"]
        # Repurposing only needs platform + topic anchors, not full briefs. Pass a compact,
        # capped summary so the prompt stays small (and never trips the max_prompt limit) even
        # for large calendars.
        compact_topics = json.dumps(
            [
                {"slot_id": item.slot_id, "platform": item.platform, "pillar": item.pillar, "topic": item.topic}
                for item in topic_plan.items[:12]
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": repurposing_prompt(request, compact_topics)},
        ]
        tier = _stage_tier(cfg, "build_repurposing_map", "cheap")
        structured, stage_costs, used, blocked = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="build_repurposing_map",
            tier=tier,
            messages=messages,
            response_schema=RepurposingMapPackage,
        )
        candidate = _usable_repurposing(structured, request)
        repurposing = candidate or _repurposing_fallback(request, topic_plan)
        return {
            "repurposing": repurposing,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
            "budget_limited": bool(state.get("budget_limited")) or blocked,
        }

    return build_map


def make_analyze_balance_and_gaps_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def analyze(state: Agent05State) -> dict[str, Any]:
        request = state["request"]
        calendar = _calendar_items(request, state.get("topic_plan"), state.get("content_briefs"))
        weekly = _period_plans(calendar, mode="week")
        monthly = _period_plans(calendar, mode="month")
        platform_summary = _platform_summaries(calendar)
        analysis = _balance_analysis(request, calendar)
        with tel.span("analyze_balance_and_gaps") as span_id:
            tel.log("analyze_balance_and_gaps.complete", span_id=span_id)
        return {
            "weekly_plan": weekly,
            "monthly_plan": monthly,
            "platform_plan_summary": platform_summary,
            "balance_gap_analysis": analysis,
        }

    return analyze


def make_run_risk_checks_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def run_risks(state: Agent05State) -> dict[str, Any]:
        report = build_risk_report(
            request=state.get("request"),
            validation_errors=state.get("validation_errors", ()),
            topic_plan=state.get("topic_plan"),
            content_briefs=state.get("content_briefs"),
            repurposing=state.get("repurposing"),
            balance_gap_analysis=state.get("balance_gap_analysis"),
        )
        with tel.span("run_risk_checks") as span_id:
            tel.log("run_risk_checks.complete", span_id=span_id, risk_count=len(report.risk_flags))
        return {"risk_report": report}

    return run_risks


def make_score_output_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def score_node(state: Agent05State) -> dict[str, Any]:
        score = score_output(
            request=state.get("request"),
            topic_plan=state.get("topic_plan"),
            content_briefs=state.get("content_briefs"),
            repurposing=state.get("repurposing"),
            balance_gap_analysis=state.get("balance_gap_analysis"),
            risk_report=state["risk_report"],
            validation_errors=state.get("validation_errors", ()),
        )
        with tel.span("score_output") as span_id:
            tel.metric("quality.overall_score", score.total_score, node="score_output")
            tel.log("score_output.complete", span_id=span_id, score=score.total_score)
        return {"quality_score": score}

    return score_node


def make_assemble_package_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 30.0))

    def assemble(state: Agent05State) -> dict[str, Any]:
        stage_costs = list(state.get("cost_usage", []))
        total = round(total_cost_inr(stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
        status = _determine_status(state, total=total, ceiling_inr=ceiling_inr)
        notes = _determine_notes(state, status)
        request = state.get("request")
        topic_plan = state.get("topic_plan")
        briefs = state.get("content_briefs")
        calendar = _calendar_items(request, topic_plan, briefs) if request else ()
        ctas = tuple(
            CTARecommendation(calendar_item_id=item.brief_id, cta=item.primary_cta, reason=item.objective)
            for item in calendar
        )
        score = state.get("quality_score")
        risks = state.get("risk_report")
        analysis = state.get("balance_gap_analysis")
        package = EditorialPlanningPackage(
            status=status,  # type: ignore[arg-type]
            package_id=state.get("request_id", ""),
            request_summary=_request_summary(request) if request else "",
            quality_score=score,
            pass_status="pass" if score and score.passed else "fail",
            editorial_calendar=calendar,
            weekly_plan=state.get("weekly_plan", ()),
            monthly_plan=state.get("monthly_plan", ()),
            platform_plan=state.get("platform_plan_summary", ()),
            content_briefs=briefs.briefs if briefs else (),
            cta_recommendations=ctas,
            repurposing_map=state.get("repurposing").items if state.get("repurposing") else (),
            balance_gap_analysis=analysis,
            risk_flags=risks.risk_flags if risks else (),
            review_notes=_review_notes(state, status),
            cost=cost,
            notes=notes,
            generation_used_llm=bool(state.get("generation_used_llm", False)),
        )
        with tel.span("assemble_package") as span_id:
            tel.metric("total.cost_inr", total, node="assemble_package")
            tel.log("assemble_package.complete", span_id=span_id, status=status)
        return {"status": status, "cost": cost, "final_output": package}

    return assemble


def _request_summary(request: Agent05Request) -> str:
    return (
        f"{request.brand_name}: {request.campaign_theme} for {request.target_audience}; "
        f"goal: {request.business_goal}; platforms: {', '.join(request.platforms)}."
    )


def _determine_status(state: Agent05State, *, total: float, ceiling_inr: float) -> str:
    if not state.get("cost_gate_ok", True) or total > ceiling_inr:
        return "stopped_cost_ceiling"
    if state.get("error_state") is not None:
        return "error"
    if state.get("status") == "needs_more_input":
        return "needs_more_input"
    # Budget forced one or more stages to fall back before their LLM call. The package is
    # partial-but-useful (deterministic output), so surface it for human review rather than
    # marking it a clean pass or a hard cost stop.
    if state.get("budget_limited"):
        return "needs_review_budget_limited"
    score = state.get("quality_score")
    if score is not None and score.passed:
        return "pass"
    return "needs_human"


def _determine_notes(state: Agent05State, status: str) -> str:
    if status == "stopped_cost_ceiling":
        return "Cost ceiling reached; run stopped before generating more editorial planning output."
    if status == "error":
        error = state.get("error_state", {})
        return f"Error in {error.get('node', 'unknown')} ({error.get('kind', 'Error')})"
    if status == "needs_more_input":
        return state.get("notes", "Editorial planning request needs required campaign fields.")
    if status == "needs_review_budget_limited":
        return (
            "Budget limit reached: some stages used deterministic fallbacks to stay under the "
            "cost ceiling. The plan is partial but usable; a human should review and optionally "
            "re-run a smaller date range or fewer platforms for richer LLM output."
        )
    if status == "pass":
        return "Review-ready Editorial Planning Package generated. No external action was taken."
    risks = state.get("risk_report")
    if risks and risks.hard_fail_codes:
        return "Hard-fail editorial planning risks require human review: " + ", ".join(risks.hard_fail_codes)
    return "Editorial planning score did not pass the threshold; human editor should review suggestions."


def _review_notes(state: Agent05State, status: str) -> tuple[str, ...]:
    if status == "needs_more_input":
        return tuple(state.get("validation_errors", ()))
    notes = [
        "Planning-only output; no publishing, scheduling, calendar, social, analytics, CMS, email, or external write action was taken.",
        "Review dates, workload, claims, and CTAs before assigning production.",
    ]
    if state.get("budget_limited"):
        notes.append(
            "Budget-limited run: lower-priority briefs are deterministic summaries; "
            "expand them or re-run a smaller plan for fuller LLM output."
        )
    risks = state.get("risk_report")
    if risks and risks.risk_flags:
        notes.append("Review risk flags before handing briefs to content creators.")
    return tuple(notes)


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 05's cloud-neutral LangGraph workflow."""
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 30.0))
    nodes = {
        "intake_validate": _node_with_error_guard(
            "intake_validate", make_intake_validate_node(cfg, llm, tel), tel=tel
        ),
        "normalize_request": _node_with_error_guard(
            "normalize_request", make_normalize_request_node(cfg, llm, tel), tel=tel
        ),
        "validate_date_and_frequency": _node_with_error_guard(
            "validate_date_and_frequency", make_validate_date_and_frequency_node(cfg, llm, tel), tel=tel
        ),
        "build_calendar_skeleton": _node_with_error_guard(
            "build_calendar_skeleton", make_build_calendar_skeleton_node(cfg, llm, tel), tel=tel
        ),
        "map_platform_strategy": _node_with_error_guard(
            "map_platform_strategy", make_map_platform_strategy_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "generate_topic_plan": _node_with_error_guard(
            "generate_topic_plan", make_generate_topic_plan_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "generate_content_briefs": _node_with_error_guard(
            "generate_content_briefs", make_generate_content_briefs_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "build_repurposing_map": _node_with_error_guard(
            "build_repurposing_map", make_build_repurposing_map_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "analyze_balance_and_gaps": _node_with_error_guard(
            "analyze_balance_and_gaps", make_analyze_balance_and_gaps_node(cfg, llm, tel), tel=tel
        ),
        "run_risk_checks": _node_with_error_guard(
            "run_risk_checks", make_run_risk_checks_node(cfg, llm, tel), tel=tel
        ),
        "score_output": _node_with_error_guard(
            "score_output", make_score_output_node(cfg, llm, tel), tel=tel
        ),
        "assemble_package": _safe_assemble_wrapper(make_assemble_package_node(cfg, llm, tel)),
    }

    def _emit_route(node: str, decision: str, target: str) -> None:
        try:
            tel.log("route.decision", node=node, decision=decision, target=target)
        except Exception:
            pass

    def route_basic(node: str, target: str):
        def route(state: Agent05State) -> str:
            if state.get("error_state") is not None:
                _emit_route(node, "error", "assemble_package")
                return "assemble_package"
            if not state.get("cost_gate_ok", True):
                _emit_route(node, "cost_ceiling", "assemble_package")
                return "assemble_package"
            _emit_route(node, "ok", target)
            return target

        return route

    def route_after_intake(state: Agent05State) -> str:
        if state.get("error_state") is not None:
            _emit_route("intake_validate", "error", "assemble_package")
            return "assemble_package"
        if state.get("status") == "needs_more_input":
            _emit_route("intake_validate", "needs_more_input", "assemble_package")
            return "assemble_package"
        _emit_route("intake_validate", "ok", "normalize_request")
        return "normalize_request"

    graph = StateGraph(Agent05State)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.set_entry_point("intake_validate")
    edges = (
        ("normalize_request", "validate_date_and_frequency"),
        ("validate_date_and_frequency", "build_calendar_skeleton"),
        ("build_calendar_skeleton", "map_platform_strategy"),
        ("map_platform_strategy", "generate_topic_plan"),
        ("generate_topic_plan", "generate_content_briefs"),
        ("generate_content_briefs", "build_repurposing_map"),
        ("build_repurposing_map", "analyze_balance_and_gaps"),
        ("analyze_balance_and_gaps", "run_risk_checks"),
        ("run_risk_checks", "score_output"),
        ("score_output", "assemble_package"),
    )
    graph.add_conditional_edges(
        "intake_validate",
        route_after_intake,
        {"normalize_request": "normalize_request", "assemble_package": "assemble_package"},
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
