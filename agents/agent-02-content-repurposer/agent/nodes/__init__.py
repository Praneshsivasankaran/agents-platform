"""LangGraph node factories for Agent 02."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from core.cost import (
    CostCeilingExceeded,
    authorize_call,
    estimate_prompt_tokens,
    resolve_is_mock,
    usage_cost_inr,
)
from core.interfaces import BillableProviderError, LLMResponse, ObjectStorage, Telemetry
from core.interfaces.llm import LLMProvider, Tier

from ..prompts import (
    build_system,
    factual_review_prompt,
    generation_prompt,
    review_prompt,
    revision_prompt,
)
from ..schemas import (
    Agent02Request,
    BillableNodeError,
    CostUsage,
    LLMDraftBundle,
    MetadataItem,
    Platform,
    RepurposedContentPackage,
    SourceContent,
    StageCost,
)
from ..state import Agent02State
from ..tools import best_effort_store_package
from ..validators import (
    _GENERIC_PHRASES,
    build_audience_value,
    build_core_message,
    build_markdown_package,
    check_factual_consistency,
    coerce_llm_drafts,
    cta_options,
    display_platform,
    generate_angles,
    hashtag_sets,
    hard_fail_status,
    make_platform_drafts,
    normalize_platform,
    parse_source,
    platform_rules,
    quality_review,
    revise_drafts,
    select_strategy,
    selected_platforms,
    source_body,
    usefulness_review,
    validate_all_platforms,
    validate_source_for_agent02,
)


def _as_metadata_items(value: object) -> tuple[MetadataItem, ...]:
    if isinstance(value, dict):
        return tuple(MetadataItem(key=str(k), value=str(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(
            item if isinstance(item, MetadataItem) else MetadataItem.model_validate(item)
            for item in value
        )
    return ()


def _normalize_platforms(value: object) -> tuple[Platform, ...]:
    if value is None or value == "":
        return ()
    raw = value if isinstance(value, (list, tuple)) else (value,)
    return tuple(dict.fromkeys(normalize_platform(str(item)) for item in raw))


def _request_from_state(state: Agent02State) -> Agent02Request:
    existing = state.get("request")
    if isinstance(existing, Agent02Request):
        return existing
    raw = state.get("raw_input")
    if isinstance(raw, Agent02Request):
        return raw
    if isinstance(raw, SourceContent):
        return Agent02Request(source=raw)
    if isinstance(raw, str):
        return Agent02Request(
            source=SourceContent(source_type="raw_article_text", full_text=raw)
        )
    if not isinstance(raw, dict):
        raise ValueError("Agent 02 input must be a dict, SourceContent, Agent02Request, or raw text")

    data = dict(raw)
    source_raw = data.get("source")
    if source_raw is None:
        source_keys = {
            "source_type",
            "title",
            "summary",
            "full_text",
            "blog_body",
            "seo_keywords",
            "suggested_tags",
            "meta_description",
            "source_status",
            "human_approved",
            "source_metadata",
        }
        source_raw = {k: data.get(k) for k in source_keys if k in data}
    if not isinstance(source_raw, dict):
        raise ValueError("Agent 02 input requires a source object or serialized source fields")
    source_data = dict(source_raw)
    if "source_type" not in source_data:
        source_data["source_type"] = "raw_article_text"
    if "source_metadata" in source_data:
        source_data["source_metadata"] = _as_metadata_items(source_data.get("source_metadata"))
    target_platforms = data.get("target_platforms", data.get("platforms", ()))
    request_data = {
        "source": SourceContent.model_validate(source_data),
        "target_platforms": _normalize_platforms(target_platforms),
        "include_newsletter": bool(data.get("include_newsletter", False)),
        "audience": str(data.get("audience", "") or ""),
        "brand_tone": str(data.get("brand_tone", "") or ""),
        "campaign_goal": str(data.get("campaign_goal", "") or ""),
        "cta": str(data.get("cta", "") or ""),
    }
    return Agent02Request.model_validate(request_data)


def _stage_tier(cfg: dict, stage_name: str, default: Tier) -> Tier:
    """Resolve the model tier for a stage from config (``llm.stage_tiers``), with a per-stage default.

    Lets cost/reliability tuning live in config rather than code. Agent 02 generates and revises
    drafts on the **cheap (flash)** tier: flash returns the structured ``LLMDraftBundle`` reliably
    (strong/pro intermittently truncates it via variable reasoning) and the deterministic validators
    still enforce factual consistency, platform fit, usefulness, CTA quality, and hard-fails afterward.
    """
    tier = cfg.get("llm", {}).get("stage_tiers", {}).get(stage_name, default)
    if tier == "cheap":
        return "cheap"
    if tier == "strong":
        return "strong"
    raise ValueError(
        f"llm.stage_tiers[{stage_name!r}]={tier!r} must be 'cheap' or 'strong'"
    )


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
    state: Agent02State,
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

    # Include the response schema in the conservative prompt-token estimate so the cost reserve
    # accounts for the JSON schema embedded in a structured-output request.
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
    params: dict[str, Any] = {}
    if auth.max_tokens is not None:
        params["max_tokens"] = min(auth.max_tokens, max_output) if max_output > 0 else auth.max_tokens
    params["_authorized_prompt_tokens"] = prompt_tokens_est

    try:
        with tel.span(stage_name) as span_id:
            try:
                response = llm.respond(
                    messages, tier=tier, params=params, response_schema=response_schema
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


def _log_provider_hiccup(tel: Telemetry, stage_name: str, kind: str) -> None:
    """Record a tolerated (non-fatal) provider failure; telemetry must never break the run."""
    try:
        tel.log(f"{stage_name}.provider_hiccup", node=stage_name, kind=kind)
    except Exception:
        pass


def _best_effort_llm_call(
    *,
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    state: Agent02State,
    stage_name: str,
    tier: Tier,
    messages: list[dict],
    downstream_stages: tuple[str, ...] = (),
    response_schema: type | None = None,
) -> tuple[object | None, list[StageCost], bool]:
    """Call the LLM but never let a transient provider/parse failure fail the run.

    Returns ``(structured, stage_costs, hiccup)``:
    - ``structured`` is the validated structured payload, or ``None`` when the call could not be
      used (so the caller falls back to its deterministic source of truth).
    - ``stage_costs`` preserves any incurred cost (a billable provider failure still bills).
    - ``hiccup`` is True when the LLM call failed and was tolerated.

    ``CostCeilingExceeded`` is deliberately re-raised — a budget rejection is NOT a hiccup and must
    still route to ``stopped_cost_ceiling``. Deterministic validators remain the source of truth.
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
        return response.structured, [stage_cost], False
    except CostCeilingExceeded:
        raise  # genuine budget stop — not a transient hiccup
    except BillableNodeError as be:
        # Provider/transient/parse failure that incurred (or may have incurred) cost.
        _log_provider_hiccup(tel, stage_name, type(be.cause).__name__)
        return None, [be.stage_cost], True
    except Exception as exc:  # noqa: BLE001 — a transient LLM-call failure must not fail the run
        _log_provider_hiccup(tel, stage_name, type(exc).__name__)
        return None, [], True


def _first_cost(stage_costs: list[StageCost], stage_name: str, tier: Tier) -> StageCost:
    """The incurred StageCost to preserve when post-call deterministic work fails (zero if none)."""
    if stage_costs:
        return stage_costs[0]
    return StageCost(stage=stage_name, cost_inr=0.0, tier=tier)


def make_intake_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm

    def intake(state: Agent02State) -> dict[str, Any]:
        with tel.span("intake") as span_id:
            request = _request_from_state(state)
            platforms = selected_platforms(request)
            tel.log(
                "intake.accepted",
                span_id=span_id,
                platform_count=len(platforms),
                source_type=request.source.source_type,
            )
            return {
                "request_id": state.get("request_id") or f"agent02-{uuid4().hex[:12]}",
                "request": request.validated_copy(target_platforms=platforms),
                "revision_count": 0,
                "cost_usage": [],
                "hard_fails": [],
                "cost_gate_ok": True,
                "status": "running",
            }

    return intake


def make_validate_source_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def validate_source(state: Agent02State) -> dict[str, Any]:
        request = state["request"]
        usable, reason = validate_source_for_agent02(request.source)
        with tel.span("validate_source") as span_id:
            tel.log("validate_source.complete", span_id=span_id, usable=usable)
        if not usable:
            return {"status": "needs_more_input", "notes": reason or "Source content is insufficient."}
        return {}

    return validate_source


def make_parse_source_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def parse_source_node(state: Agent02State) -> dict[str, Any]:
        parsed = parse_source(state["request"].source)
        with tel.span("parse_source") as span_id:
            tel.log(
                "parse_source.complete",
                span_id=span_id,
                claim_count=len(parsed.source_claims),
                confidential_count=len(parsed.confidential_flags),
            )
        return {"parsed_source": parsed}

    return parse_source_node


def make_extract_core_message_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def extract_core_message(state: Agent02State) -> dict[str, Any]:
        core = build_core_message(state["parsed_source"])
        with tel.span("extract_core_message") as span_id:
            tel.log("extract_core_message.complete", span_id=span_id)
        return {"core_message": core}

    return extract_core_message


def make_extract_audience_value_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def extract_audience_value(state: Agent02State) -> dict[str, Any]:
        value = build_audience_value(state["request"], state["parsed_source"])
        with tel.span("extract_audience_value") as span_id:
            tel.log("extract_audience_value.complete", span_id=span_id)
        return {"audience_value": value}

    return extract_audience_value


def make_generate_content_angles_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def generate_content_angles(state: Agent02State) -> dict[str, Any]:
        angles = generate_angles(state["parsed_source"], selected_platforms(state["request"]))
        with tel.span("generate_content_angles") as span_id:
            tel.log("generate_content_angles.complete", span_id=span_id, angle_count=len(angles))
        return {"content_angles": angles}

    return generate_content_angles


def make_select_platform_strategy_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def select_platform_strategy(state: Agent02State) -> dict[str, Any]:
        strategy = select_strategy(
            state["request"],
            selected_platforms(state["request"]),
            state["content_angles"],
        )
        with tel.span("select_platform_strategy") as span_id:
            tel.log("select_platform_strategy.complete", span_id=span_id, platform_count=len(strategy))
        return {"platform_strategy": strategy}

    return select_platform_strategy


def make_load_platform_rules_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def load_platform_rules(state: Agent02State) -> dict[str, Any]:
        rules = platform_rules(selected_platforms(state["request"]))
        with tel.span("load_platform_rules") as span_id:
            tel.log("load_platform_rules.complete", span_id=span_id, rule_count=len(rules))
        return {"platform_rules": rules}

    return load_platform_rules


def make_generate_platform_drafts_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def generate_platform_drafts(state: Agent02State) -> dict[str, Any]:
        request = state["request"]
        parsed = state["parsed_source"]
        campaign = (
            f"Audience: {request.audience or 'target audience'}\n"
            f"Brand tone: {request.brand_tone or 'professional'}\n"
            f"Campaign goal: {request.campaign_goal or 'repurpose source content'}\n"
            f"CTA: {request.cta or 'Read the full piece'}"
        )
        plan = "\n".join(
            f"{display_platform(strategy.platform)}: {strategy.content_type}, angle={strategy.angle_id}"
            for strategy in state["platform_strategy"]
        )
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {
                "role": "user",
                "content": generation_prompt(
                    source=source_body(request.source),
                    campaign_context=campaign,
                    platform_plan=plan,
                    avoid_phrases=_GENERIC_PHRASES,
                ),
            },
        ]
        tier = _stage_tier(cfg, "generate_platform_drafts", "cheap")
        # Best-effort: a provider/transient/parse failure here falls back to deterministic
        # templates rather than failing the run (cost preserved). CostCeilingExceeded still stops.
        structured, stage_costs, _hiccup = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="generate_platform_drafts",
            tier=tier,
            messages=messages,
            downstream_stages=("check_factual_consistency", "review_quality"),
            response_schema=LLMDraftBundle,
        )
        try:
            core_message = state["core_message"]
            audience_value = state["audience_value"]
            strategy = state["platform_strategy"]
            template_drafts = make_platform_drafts(
                request, parsed, core_message, audience_value, strategy
            )
            bundle = structured if isinstance(structured, LLMDraftBundle) else None
            if bundle is not None:
                drafts, used = coerce_llm_drafts(
                    request,
                    parsed,
                    core_message,
                    audience_value,
                    strategy,
                    bundle,
                    base_drafts=template_drafts,
                )
            else:
                drafts, used = template_drafts, 0
            tel.log(
                "generate_platform_drafts.complete",
                llm_drafts_used=used,
                total_drafts=len(drafts),
                fell_back=used == 0,
            )
            return {"platform_drafts": drafts, "cost_usage": stage_costs}
        except Exception as exc:
            raise BillableNodeError(_first_cost(stage_costs, "generate_platform_drafts", tier), exc) from exc

    return generate_platform_drafts


def make_validate_platform_fit_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def validate_platform_fit(state: Agent02State) -> dict[str, Any]:
        report = validate_all_platforms(state["platform_drafts"], state["platform_rules"])
        with tel.span("validate_platform_fit") as span_id:
            tel.log("validate_platform_fit.complete", span_id=span_id, failed=sum(1 for r in report if not r.passed))
        return {"platform_validation_report": report}

    return validate_platform_fit


def make_check_factual_consistency_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def check_node(state: Agent02State) -> dict[str, Any]:
        claim_text = "\n".join(f"{claim.claim_id}: {claim.text}" for claim in state["parsed_source"].source_claims)
        draft_text = "\n\n".join(f"{d.platform}: {d.body or d.voiceover}" for d in state["platform_drafts"])
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": factual_review_prompt(source_claims=claim_text, drafts=draft_text)},
        ]
        tier = _stage_tier(cfg, "check_factual_consistency", "strong")
        # The deterministic factual validator is the source of truth; the LLM response is not used,
        # so a provider hiccup here must not fail the run (cost preserved, validator still runs).
        _structured, stage_costs, _hiccup = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="check_factual_consistency",
            tier=tier,
            messages=messages,
            downstream_stages=("review_quality",),
        )
        try:
            report = check_factual_consistency(state["parsed_source"], state["platform_drafts"])
            return {"factual_consistency_report": report, "cost_usage": stage_costs}
        except Exception as exc:
            raise BillableNodeError(_first_cost(stage_costs, "check_factual_consistency", tier), exc) from exc

    return check_node


def make_usefulness_review_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def review_usefulness(state: Agent02State) -> dict[str, Any]:
        report = usefulness_review(state["platform_drafts"])
        with tel.span("usefulness_review") as span_id:
            tel.metric("quality.usefulness", report.score, node="usefulness_review")
            tel.log("usefulness_review.complete", span_id=span_id, score=report.score)
        return {"usefulness_report": report}

    return review_usefulness


def make_review_quality_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def review_quality_node(state: Agent02State) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {
                "role": "user",
                "content": review_prompt(
                    source=source_body(state["request"].source),
                    drafts="\n\n".join(d.model_dump_json() for d in state["platform_drafts"]),
                    validation="\n".join(v.model_dump_json() for v in state["platform_validation_report"]),
                    factual=state["factual_consistency_report"].model_dump_json(),
                    usefulness=state["usefulness_report"].model_dump_json(),
                ),
            },
        ]
        tier = _stage_tier(cfg, "review_quality", "strong")
        # Deterministic quality_review is the authoritative gate; the LLM response is not used, so a
        # provider hiccup must not fail the run (cost preserved, scoring still runs).
        _structured, stage_costs, _hiccup = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="review_quality",
            tier=tier,
            messages=messages,
        )
        try:
            report = quality_review(
                state["platform_validation_report"],
                state["factual_consistency_report"],
                state["usefulness_report"],
                state["platform_drafts"],
                state["parsed_source"].confidential_flags,
            )
            tel.metric("quality.overall_score", report.overall_score, node="review_quality")
            update: dict[str, Any] = {"quality_report": report, "cost_usage": stage_costs}
            if report.hard_fails:
                update["hard_fails"] = list(report.hard_fails)
            return update
        except Exception as exc:
            raise BillableNodeError(_first_cost(stage_costs, "review_quality", tier), exc) from exc

    return review_quality_node


def make_revise_weak_outputs_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def revise_weak_outputs(state: Agent02State) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {
                "role": "user",
                "content": revision_prompt(
                    source=source_body(state["request"].source),
                    drafts="\n\n".join(d.model_dump_json() for d in state["platform_drafts"]),
                    issues="\n".join(state["quality_report"].improvement_suggestions),
                    avoid_phrases=_GENERIC_PHRASES,
                ),
            },
        ]
        tier = _stage_tier(cfg, "revise_weak_outputs", "cheap")
        # Best-effort: a provider hiccup falls back to the deterministic revision baseline rather
        # than failing the run (cost preserved). CostCeilingExceeded still stops.
        structured, stage_costs, _hiccup = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="revise_weak_outputs",
            tier=tier,
            messages=messages,
            downstream_stages=("check_factual_consistency", "review_quality"),
            response_schema=LLMDraftBundle,
        )
        try:
            # Deterministic revision baseline always applies (guardrail fixes for the flagged
            # hard-fails); a usable LLM revision is then layered over that baseline.
            revised = revise_drafts(state["platform_drafts"], state["quality_report"])
            bundle = structured if isinstance(structured, LLMDraftBundle) else None
            used = 0
            if bundle is not None:
                revised, used = coerce_llm_drafts(
                    state["request"],
                    state["parsed_source"],
                    state["core_message"],
                    state["audience_value"],
                    state["platform_strategy"],
                    bundle,
                    base_drafts=revised,
                )
            revision_count = int(state.get("revision_count", 0)) + 1
            tel.metric("revision.count", revision_count, node="revise_weak_outputs")
            tel.log("revise_weak_outputs.complete", llm_drafts_used=used)
            return {
                "platform_drafts": revised,
                "revision_count": revision_count,
                "cost_usage": stage_costs,
            }
        except Exception as exc:
            raise BillableNodeError(_first_cost(stage_costs, "revise_weak_outputs", tier), exc) from exc

    return revise_weak_outputs


def make_finalize_node(
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    object_storage: ObjectStorage | None = None,
):
    _ = llm
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 30.0))
    output_cfg = cfg.get("output_storage", {})
    storage_enabled = bool(output_cfg.get("enabled", False))
    output_prefix = str(output_cfg.get("prefix", cfg.get("object_storage", {}).get("prefix", "content-repurposer/")))

    def finalize(state: Agent02State) -> dict[str, Any]:
        stage_costs = list(state.get("cost_usage", []))
        total = round(sum(stage.cost_inr for stage in stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
        status = _determine_status(state, total=total, ceiling_inr=ceiling_inr)
        notes = _determine_notes(state, status)
        request = state.get("request")
        parsed = state.get("parsed_source")
        core_msg = state.get("core_message")
        quality = state.get("quality_report")
        drafts = state.get("platform_drafts", ())
        markdown = build_markdown_package(
            parsed.title if parsed else "",
            drafts,
            quality,
            notes=notes,
        ) if drafts else ""
        current_fails = tuple(quality.hard_fails) if quality and status != "pass" else ()
        package = RepurposedContentPackage(
            status=status,  # type: ignore[arg-type]
            package_id=state.get("request_id", ""),
            source_summary=parsed.summary if parsed else "",
            content_brief=core_msg.main_message if core_msg else "",
            platform_outputs=drafts,
            markdown_review_package=markdown,
            output_package_uri=None,
            validation_report=state.get("platform_validation_report", ()),
            factual_consistency_report=state.get("factual_consistency_report"),
            usefulness_report=state.get("usefulness_report"),
            quality_report=quality,
            cta_options=cta_options(request) if request else (),
            hashtag_sets=hashtag_sets(drafts),
            cost=cost,
            hard_fails=current_fails,
            improvement_suggestions=quality.improvement_suggestions if quality else (),
            notes=notes,
            revision_count=int(state.get("revision_count", 0)),
        )
        uri = None
        if storage_enabled:
            uri = best_effort_store_package(
                storage=object_storage,
                tel=tel,
                package=package,
                prefix=output_prefix,
            )
            if uri:
                package = package.validated_copy(output_package_uri=uri)
        with tel.span("finalize") as span_id:
            tel.metric("total.cost_inr", total, node="finalize")
            tel.log("finalize.complete", span_id=span_id, status=status)
        return {
            "status": status,
            "markdown_review_package": markdown,
            "output_package_uri": uri,
            "final_output": package,
        }

    return finalize


def _determine_status(state: Agent02State, *, total: float, ceiling_inr: float) -> str:
    if not state.get("cost_gate_ok", True) or total > ceiling_inr:
        return "stopped_cost_ceiling"
    if state.get("error_state") is not None:
        return "error"
    if state.get("status") == "needs_more_input":
        return "needs_more_input"
    decision = hard_fail_status(state.get("quality_report"))
    if decision == "pass":
        return "pass"
    if decision == "needs_human":
        return "needs_human"
    return "needs_human"


def _determine_notes(state: Agent02State, status: str) -> str:
    if status == "stopped_cost_ceiling":
        return "Cost ceiling reached; run stopped to protect the Rs.30/package budget."
    if status == "error":
        error_state = state.get("error_state", {})
        return f"Error in {error_state.get('node', 'unknown')} ({error_state.get('kind', 'Error')})"
    if status == "needs_more_input":
        return state.get("notes", "Source content is too thin or incomplete for repurposing.")
    if status == "pass":
        return "Review-ready draft package generated. No publishing or external write action was taken."
    quality = state.get("quality_report")
    if quality and quality.hard_fails:
        terminal = [h.reason for h in quality.hard_fails if h.severity == "terminal"]
        if terminal:
            return "Terminal hard-fail: " + "; ".join(terminal)
    return "Quality gate did not pass within revision/cost limits; human review required."


__all__ = [
    "make_check_factual_consistency_node",
    "make_extract_audience_value_node",
    "make_extract_core_message_node",
    "make_finalize_node",
    "make_generate_content_angles_node",
    "make_generate_platform_drafts_node",
    "make_intake_node",
    "make_load_platform_rules_node",
    "make_parse_source_node",
    "make_review_quality_node",
    "make_revise_weak_outputs_node",
    "make_select_platform_strategy_node",
    "make_usefulness_review_node",
    "make_validate_platform_fit_node",
    "make_validate_source_node",
]
