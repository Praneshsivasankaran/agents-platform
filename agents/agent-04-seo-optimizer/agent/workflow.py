"""LangGraph workflow for Agent 04 - SEO Optimization Agent."""
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
    estimate_prompt_tokens,
    resolve_is_mock,
    total_cost_inr,
    usage_cost_inr,
)
from core.interfaces import BillableProviderError, LLMResponse, Telemetry
from core.interfaces.llm import LLMProvider, Tier

from .prompts import (
    build_system,
    faqs_prompt,
    headings_prompt,
    metadata_prompt,
    optimized_draft_prompt,
    readability_prompt,
)
from .schemas import (
    Agent04Request,
    BillableNodeError,
    CostUsage,
    DraftAnalysis,
    FAQBundle,
    FAQItem,
    HeadingItem,
    HeadingPlan,
    KeywordPlacement,
    KeywordPlan,
    MetadataPackage,
    OptimizedDraftPackage,
    ReadabilityReport,
    SEOOptimizationPackage,
    StageCost,
)
from .scoring import build_risk_report, score_output
from .state import Agent04State
from .tools import (
    clean_text,
    count_words,
    detect_cta_presence,
    estimate_readability,
    extract_headings,
    first_sentence,
    keyword_density_check,
    last_sentence,
    simple_keyword_presence,
    slugify,
    split_secondary_keywords,
    top_terms,
)


_ALIASES = {
    "draft": "draft_content",
    "content": "draft_content",
    "article": "draft_content",
    "title": "topic",
    "topic_title": "topic",
    "keyword": "primary_keyword",
    "secondary": "secondary_keywords",
    "audience": "target_audience",
    "goal": "content_goal",
    "tone": "brand_tone",
    "cta": "cta_direction",
}

_BILLABLE_STAGES = (
    "generate_metadata",
    "optimize_headings",
    "review_readability",
    "generate_faqs",
    "optimize_draft",
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
            pkg = SEOOptimizationPackage(
                status="error",
                cost=cost,
                notes=f"Fatal error in assemble_package ({type(exc).__name__})",
            )
            return {"final_output": pkg, "status": "error"}

    safe_assemble.__name__ = "safe_assemble_package"
    return safe_assemble


def _request_from_state(state: Agent04State) -> Agent04Request:
    existing = state.get("request")
    if isinstance(existing, Agent04Request):
        return existing
    raw = state.get("raw_input")
    if isinstance(raw, Agent04Request):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("Agent 04 input must be a serialized SEO optimization request")
    data = dict(raw)
    for old_key, new_key in _ALIASES.items():
        if old_key in data and new_key not in data:
            data[new_key] = data[old_key]
    if "secondary_keywords" in data:
        data["secondary_keywords"] = split_secondary_keywords(data["secondary_keywords"])
    if "constraints" in data:
        data["constraints"] = split_secondary_keywords(data["constraints"])
    return Agent04Request.model_validate(data)


def _safe_validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        fields = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "input"
            fields.append(loc)
        return "Missing or invalid SEO request fields: " + ", ".join(dict.fromkeys(fields))
    return "Invalid Agent 04 input: " + type(exc).__name__


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
    state: Agent04State,
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
    state: Agent04State,
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
        return response.structured, [stage_cost], True
    except CostCeilingExceeded:
        raise
    except BillableNodeError as be:
        _log_provider_hiccup(tel, stage_name, type(be.cause).__name__)
        return None, [be.stage_cost], False
    except Exception as exc:  # noqa: BLE001
        _log_provider_hiccup(tel, stage_name, type(exc).__name__)
        return None, [], False


def _log_provider_hiccup(tel: Telemetry, stage_name: str, kind: str) -> None:
    try:
        tel.log(f"{stage_name}.provider_hiccup", node=stage_name, kind=kind)
    except Exception:
        pass


def _is_generic_text(value: str) -> bool:
    text = clean_text(value).lower()
    return not text or len(text) < 8 or set(text) <= {"x"}


def _usable_metadata(candidate: object) -> MetadataPackage | None:
    if not isinstance(candidate, MetadataPackage):
        return None
    fields = (candidate.meta_description, candidate.url_slug, candidate.recommended_h1)
    if any(_is_generic_text(field) for field in fields):
        return None
    if not candidate.seo_title_options or any(_is_generic_text(title) for title in candidate.seo_title_options):
        return None
    return candidate


def _metadata_fallback(request: Agent04Request) -> MetadataPackage:
    base_title = clean_text(request.topic)
    keyword = clean_text(request.primary_keyword)
    title_options = (
        f"{base_title}: A Practical Guide to {keyword}",
        f"How {keyword} Helps {request.target_audience or 'Content Teams'}",
        f"{keyword} for {request.content_goal or 'Better Content Outcomes'}",
    )
    meta = (
        f"Learn how {keyword} supports {request.topic.lower()} with practical guidance, "
        f"clear structure, and review-ready next steps for human editors."
    )
    if len(meta) > 158:
        meta = meta[:155].rstrip(" ,.;") + "..."
    return MetadataPackage(
        seo_title_options=title_options,
        meta_description=meta,
        url_slug=slugify(f"{base_title} {keyword}"),
        recommended_h1=title_options[0],
    )


def _heading_fallback(request: Agent04Request, metadata: MetadataPackage) -> HeadingPlan:
    audience = request.target_audience or "the target audience"
    h2s = (
        HeadingItem(level="h2", text=f"Why {request.topic} Matters", reason="Connects the topic to reader intent."),
        HeadingItem(
            level="h2",
            text=f"How {request.primary_keyword} Supports the Goal",
            reason="Places the primary keyword in a natural section heading.",
        ),
        HeadingItem(level="h2", text=f"Practical Next Steps for {audience}", reason="Moves readers toward action."),
    )
    return HeadingPlan(
        recommended_h1=metadata.recommended_h1,
        h2_h3_plan=h2s,
        notes=("Keep headings specific and avoid repeating the primary keyword in every heading.",),
    )


def _readability_fallback(request: Agent04Request, analysis: DraftAnalysis) -> ReadabilityReport:
    fixes: list[str] = []
    if analysis.word_count > 1200:
        fixes.append("Break long sections into shorter subsections.")
    if analysis.readability_score < 50:
        fixes.append("Shorten long sentences and replace abstract wording with concrete examples.")
    if not analysis.cta_present:
        fixes.append("Add a clear CTA aligned with the requested direction.")
    if not fixes:
        fixes.append("Keep paragraphs short and make each section answer one search intent.")
    cta = request.cta_direction or "Invite the reader to review the next practical step."
    return ReadabilityReport(
        readability_score=analysis.readability_score,
        reading_level="easy" if analysis.readability_score >= 60 else "moderate",
        fixes=tuple(fixes),
        intro_improvement=(
            f"Open by naming the reader problem, then introduce {request.primary_keyword} as the practical lens."
        ),
        conclusion_improvement=(
            "Close by summarizing the main takeaway and making the next human-review step explicit."
        ),
        cta_suggestion=cta,
    )


def _faqs_fallback(request: Agent04Request) -> FAQBundle:
    keyword = request.primary_keyword
    return FAQBundle(
        faqs=(
            FAQItem(
                question=f"What is {keyword}?",
                answer=(
                    f"{keyword} is the main concept this article should explain in the context of "
                    f"{request.topic}."
                ),
            ),
            FAQItem(
                question=f"How should {keyword} be used naturally?",
                answer="Use it in the title, intro, one heading, and relevant body sections without repetition.",
            ),
            FAQItem(
                question="What should a human editor review before approval?",
                answer="Review factual claims, keyword placement, readability, CTA fit, and brand tone.",
            ),
        )
    )


def _optimized_fallback(
    request: Agent04Request,
    metadata: MetadataPackage,
    headings: HeadingPlan,
    readability: ReadabilityReport,
) -> OptimizedDraftPackage:
    original = request.draft_content.strip()
    intro = (
        f"{request.primary_keyword} matters for {request.topic} because readers need a clear, useful "
        "answer before they decide what to do next."
    )
    if simple_keyword_presence(original, request.primary_keyword):
        body = original
    else:
        body = intro + "\n\n" + original
    sections = "\n\n".join(
        f"## {item.text}\n{item.reason or 'Use this section to make the draft more specific and useful.'}"
        for item in headings.h2_h3_plan
    )
    conclusion = readability.conclusion_improvement or "Summarize the next step for the reader."
    cta = readability.cta_suggestion or request.cta_direction or "Review the draft and choose the next step."
    optimized = (
        f"# {metadata.recommended_h1}\n\n"
        f"{body}\n\n"
        f"{sections}\n\n"
        f"## Conclusion\n{conclusion}\n\n"
        f"## Next Step\n{cta}"
    )
    notes = (
        "Deterministic fallback preserved the original draft and added SEO structure.",
        "Human editor should verify any factual or numerical claims before use.",
    )
    return OptimizedDraftPackage(optimized_draft=optimized, editor_notes=notes)


def make_intake_validate_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def intake(state: Agent04State) -> dict[str, Any]:
        with tel.span("intake_validate") as span_id:
            try:
                request = _request_from_state(state)
            except Exception as exc:  # noqa: BLE001
                message = _safe_validation_message(exc)
                tel.log("intake_validate.invalid", span_id=span_id)
                return {
                    "request_id": state.get("request_id") or f"agent04-{uuid4().hex[:12]}",
                    "status": "needs_more_input",
                    "notes": message,
                    "validation_errors": (message,),
                    "cost_usage": [],
                    "cost_gate_ok": True,
                    "generation_used_llm": False,
                }
            tel.log("intake_validate.accepted", span_id=span_id)
            return {
                "request_id": state.get("request_id") or f"agent04-{uuid4().hex[:12]}",
                "request": request,
                "raw_input": request.model_dump(mode="json"),
                "status": "running",
                "cost_usage": [],
                "cost_gate_ok": True,
                "generation_used_llm": False,
            }

    return intake


def make_normalize_input_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def normalize(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        normalized = "\n".join(line.strip() for line in request.draft_content.splitlines() if line.strip())
        with tel.span("normalize_input") as span_id:
            tel.log("normalize_input.complete", span_id=span_id)
        return {"normalized_draft": normalized or request.draft_content}

    return normalize


def make_analyze_existing_draft_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def analyze(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        draft = state.get("normalized_draft") or request.draft_content
        headings = extract_headings(draft)
        readability = estimate_readability(draft)
        primary_present = simple_keyword_presence(draft, request.primary_keyword)
        issues: list[str] = []
        if count_words(draft) < 80:
            issues.append("Draft is short; human review should confirm there is enough source material.")
        if not headings:
            issues.append("Draft has no clear markdown headings.")
        if not primary_present:
            issues.append("Primary keyword is not present in the source draft.")
        if not detect_cta_presence(draft, request.cta_direction):
            issues.append("Draft does not contain a clear CTA.")
        analysis = DraftAnalysis(
            word_count=count_words(draft),
            existing_headings=headings,
            current_title=headings[0] if headings else request.topic,
            intro_present=bool(first_sentence(draft)),
            cta_present=detect_cta_presence(draft, request.cta_direction),
            primary_keyword_present=primary_present,
            primary_keyword_density=keyword_density_check(draft, request.primary_keyword),
            readability_score=readability,
            summary=first_sentence(draft),
            issues=tuple(issues),
        )
        with tel.span("analyze_existing_draft") as span_id:
            tel.log("analyze_existing_draft.complete", span_id=span_id, word_count=analysis.word_count)
        return {"analysis": analysis}

    return analyze


def make_plan_keywords_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def plan_keywords(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        draft = state.get("normalized_draft") or request.draft_content
        all_keywords = (request.primary_keyword,) + request.secondary_keywords
        placements = tuple(
            KeywordPlacement(
                keyword=keyword,
                present=simple_keyword_presence(draft, keyword),
                density=keyword_density_check(draft, keyword),
                suggested_locations=(
                    "SEO title",
                    "intro",
                    "one H2 section",
                    "conclusion or CTA",
                )
                if keyword == request.primary_keyword
                else ("supporting section", "FAQ answer"),
            )
            for keyword in all_keywords
        )
        notes = (
            "Use the primary keyword in the title, intro, one heading, and conclusion.",
            "Use secondary keywords only where they match the reader intent.",
        )
        plan = KeywordPlan(
            primary_keyword=request.primary_keyword,
            secondary_keywords=request.secondary_keywords,
            placements=placements,
            natural_usage_notes=notes,
        )
        with tel.span("plan_keywords") as span_id:
            tel.log("plan_keywords.complete", span_id=span_id)
        return {"keyword_plan": plan}

    return plan_keywords


def make_generate_metadata_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def generate_metadata(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        analysis = state["analysis"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": metadata_prompt(request, analysis.model_dump_json())},
        ]
        tier = _stage_tier(cfg, "generate_metadata", "cheap")
        structured, stage_costs, used = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="generate_metadata",
            tier=tier,
            messages=messages,
            downstream_stages=("optimize_headings", "review_readability", "generate_faqs", "optimize_draft"),
            response_schema=MetadataPackage,
        )
        metadata = _usable_metadata(structured) or _metadata_fallback(request)
        return {
            "metadata": metadata,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and structured is metadata),
        }

    return generate_metadata


def make_optimize_headings_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def optimize_headings(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        metadata = state["metadata"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": headings_prompt(request, metadata.model_dump_json())},
        ]
        tier = _stage_tier(cfg, "optimize_headings", "cheap")
        structured, stage_costs, used = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="optimize_headings",
            tier=tier,
            messages=messages,
            downstream_stages=("review_readability", "generate_faqs", "optimize_draft"),
            response_schema=HeadingPlan,
        )
        candidate = structured if isinstance(structured, HeadingPlan) and len(structured.h2_h3_plan) >= 2 else None
        if candidate is not None and _is_generic_text(candidate.recommended_h1):
            candidate = None
        headings = candidate or _heading_fallback(request, metadata)
        return {
            "heading_plan": headings,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
        }

    return optimize_headings


def make_review_readability_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def review_readability(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        headings = state["heading_plan"]
        analysis = state["analysis"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": readability_prompt(request, headings.model_dump_json())},
        ]
        tier = _stage_tier(cfg, "review_readability", "cheap")
        structured, stage_costs, used = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="review_readability",
            tier=tier,
            messages=messages,
            downstream_stages=("generate_faqs", "optimize_draft"),
            response_schema=ReadabilityReport,
        )
        candidate = structured if isinstance(structured, ReadabilityReport) else None
        if candidate is not None and _is_generic_text(candidate.reading_level):
            candidate = None
        readability = candidate or _readability_fallback(request, analysis)
        return {
            "readability": readability,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
        }

    return review_readability


def make_generate_faqs_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def generate_faqs(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        headings = state["heading_plan"]
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": faqs_prompt(request, headings.model_dump_json())},
        ]
        tier = _stage_tier(cfg, "generate_faqs", "cheap")
        structured, stage_costs, used = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="generate_faqs",
            tier=tier,
            messages=messages,
            downstream_stages=("optimize_draft",),
            response_schema=FAQBundle,
        )
        candidate = structured if isinstance(structured, FAQBundle) and structured.faqs else None
        if candidate is not None and any(_is_generic_text(item.question) for item in candidate.faqs):
            candidate = None
        faqs = candidate or _faqs_fallback(request)
        return {
            "faq_bundle": faqs,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
        }

    return generate_faqs


def make_optimize_draft_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    def optimize_draft(state: Agent04State) -> dict[str, Any]:
        request = state["request"]
        metadata = state["metadata"]
        headings = state["heading_plan"]
        readability = state["readability"]
        seo_context = {
            "metadata": metadata.model_dump(mode="json"),
            "headings": headings.model_dump(mode="json"),
            "readability": readability.model_dump(mode="json"),
            "keywords": state["keyword_plan"].model_dump(mode="json"),
        }
        messages = [
            {"role": "system", "content": build_system(cfg)},
            {"role": "user", "content": optimized_draft_prompt(request, json.dumps(seo_context, sort_keys=True))},
        ]
        tier = _stage_tier(cfg, "optimize_draft", "strong")
        structured, stage_costs, used = _best_effort_llm_call(
            cfg=cfg,
            llm=llm,
            tel=tel,
            state=state,
            stage_name="optimize_draft",
            tier=tier,
            messages=messages,
            response_schema=OptimizedDraftPackage,
        )
        candidate = structured if isinstance(structured, OptimizedDraftPackage) else None
        if candidate is not None and _is_generic_text(candidate.optimized_draft):
            candidate = None
        optimized = candidate or _optimized_fallback(request, metadata, headings, readability)
        return {
            "optimized": optimized,
            "cost_usage": stage_costs,
            "generation_used_llm": bool(state.get("generation_used_llm")) or (used and candidate is not None),
        }

    return optimize_draft


def make_run_risk_checks_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def run_risks(state: Agent04State) -> dict[str, Any]:
        report = build_risk_report(
            request=state["request"],
            analysis=state["analysis"],
            metadata=state.get("metadata"),
            heading_plan=state.get("heading_plan"),
            readability=state.get("readability"),
            faq_bundle=state.get("faq_bundle"),
            optimized=state.get("optimized"),
        )
        with tel.span("run_risk_checks") as span_id:
            tel.log("run_risk_checks.complete", span_id=span_id, risk_count=len(report.risk_flags))
        return {"risk_report": report}

    return run_risks


def make_score_output_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = (cfg, llm)

    def score_node(state: Agent04State) -> dict[str, Any]:
        score = score_output(
            request=state["request"],
            analysis=state["analysis"],
            metadata=state.get("metadata"),
            keyword_plan=state["keyword_plan"],
            heading_plan=state.get("heading_plan"),
            readability=state.get("readability"),
            faq_bundle=state.get("faq_bundle"),
            risk_report=state["risk_report"],
            optimized=state.get("optimized"),
        )
        with tel.span("score_output") as span_id:
            tel.metric("quality.overall_score", score.total_score, node="score_output")
            tel.log("score_output.complete", span_id=span_id, score=score.total_score)
        return {"seo_score": score}

    return score_node


def make_assemble_package_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    _ = llm
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 20.0))

    def assemble(state: Agent04State) -> dict[str, Any]:
        stage_costs = list(state.get("cost_usage", []))
        total = round(total_cost_inr(stage_costs), 6)
        cost = CostUsage(stage_costs=tuple(stage_costs), total_inr=total)
        status = _determine_status(state, total=total, ceiling_inr=ceiling_inr)
        notes = _determine_notes(state, status)
        score = state.get("seo_score")
        metadata = state.get("metadata")
        headings = state.get("heading_plan")
        readability = state.get("readability")
        faqs = state.get("faq_bundle")
        optimized = state.get("optimized")
        risks = state.get("risk_report")
        package = SEOOptimizationPackage(
            status=status,  # type: ignore[arg-type]
            package_id=state.get("request_id", ""),
            seo_score=score,
            pass_status="pass" if score and score.passed else "fail",
            title_options=metadata.seo_title_options if metadata else (),
            meta_description=metadata.meta_description if metadata else "",
            url_slug=metadata.url_slug if metadata else "",
            recommended_h1=metadata.recommended_h1 if metadata else "",
            heading_plan=headings.h2_h3_plan if headings else (),
            keyword_placement=state.get("keyword_plan").placements if state.get("keyword_plan") else (),
            readability_fixes=readability.fixes if readability else (),
            intro_improvement=readability.intro_improvement if readability else "",
            conclusion_improvement=readability.conclusion_improvement if readability else "",
            cta_suggestion=readability.cta_suggestion if readability else "",
            faq_suggestions=faqs.faqs if faqs else (),
            risk_flags=risks.risk_flags if risks else (),
            editor_notes=optimized.editor_notes if optimized else tuple(state.get("validation_errors", ())),
            optimized_draft=optimized.optimized_draft if optimized else "",
            cost=cost,
            notes=notes,
            generation_used_llm=bool(state.get("generation_used_llm", False)),
        )
        with tel.span("assemble_package") as span_id:
            tel.metric("total.cost_inr", total, node="assemble_package")
            tel.log("assemble_package.complete", span_id=span_id, status=status)
        return {"status": status, "cost": cost, "final_output": package}

    return assemble


def _determine_status(state: Agent04State, *, total: float, ceiling_inr: float) -> str:
    if not state.get("cost_gate_ok", True) or total > ceiling_inr:
        return "stopped_cost_ceiling"
    if state.get("error_state") is not None:
        return "error"
    if state.get("status") == "needs_more_input":
        return "needs_more_input"
    score = state.get("seo_score")
    if score is not None and score.passed:
        return "pass"
    return "needs_human"


def _determine_notes(state: Agent04State, status: str) -> str:
    if status == "stopped_cost_ceiling":
        return "Cost ceiling reached; run stopped before generating more SEO output."
    if status == "error":
        error = state.get("error_state", {})
        return f"Error in {error.get('node', 'unknown')} ({error.get('kind', 'Error')})"
    if status == "needs_more_input":
        return state.get("notes", "SEO request needs required draft, topic, and primary keyword.")
    if status == "pass":
        return "Review-ready SEO Optimization Package generated. No external action was taken."
    risks = state.get("risk_report")
    if risks and risks.hard_fail_codes:
        return "Hard-fail SEO risks require human review: " + ", ".join(risks.hard_fail_codes)
    return "SEO score did not pass the threshold; human editor should review suggestions."


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 04's cloud-neutral LangGraph workflow."""
    ceiling_inr = float(cfg.get("cost", {}).get("ceiling_inr", 20.0))
    nodes = {
        "intake_validate": _node_with_error_guard(
            "intake_validate", make_intake_validate_node(cfg, llm, tel), tel=tel
        ),
        "normalize_input": _node_with_error_guard(
            "normalize_input", make_normalize_input_node(cfg, llm, tel), tel=tel
        ),
        "analyze_existing_draft": _node_with_error_guard(
            "analyze_existing_draft", make_analyze_existing_draft_node(cfg, llm, tel), tel=tel
        ),
        "plan_keywords": _node_with_error_guard(
            "plan_keywords", make_plan_keywords_node(cfg, llm, tel), tel=tel
        ),
        "generate_metadata": _node_with_error_guard(
            "generate_metadata", make_generate_metadata_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "optimize_headings": _node_with_error_guard(
            "optimize_headings", make_optimize_headings_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "review_readability": _node_with_error_guard(
            "review_readability", make_review_readability_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "generate_faqs": _node_with_error_guard(
            "generate_faqs", make_generate_faqs_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
        ),
        "optimize_draft": _node_with_error_guard(
            "optimize_draft", make_optimize_draft_node(cfg, llm, tel), ceiling_inr=ceiling_inr, tel=tel
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
        def route(state: Agent04State) -> str:
            if state.get("error_state") is not None:
                _emit_route(node, "error", "assemble_package")
                return "assemble_package"
            if not state.get("cost_gate_ok", True):
                _emit_route(node, "cost_ceiling", "assemble_package")
                return "assemble_package"
            _emit_route(node, "ok", target)
            return target

        return route

    def route_after_intake(state: Agent04State) -> str:
        if state.get("error_state") is not None:
            _emit_route("intake_validate", "error", "assemble_package")
            return "assemble_package"
        if state.get("status") == "needs_more_input":
            _emit_route("intake_validate", "needs_more_input", "assemble_package")
            return "assemble_package"
        _emit_route("intake_validate", "ok", "normalize_input")
        return "normalize_input"

    graph = StateGraph(Agent04State)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.set_entry_point("intake_validate")
    edges = (
        ("normalize_input", "analyze_existing_draft"),
        ("analyze_existing_draft", "plan_keywords"),
        ("plan_keywords", "generate_metadata"),
        ("generate_metadata", "optimize_headings"),
        ("optimize_headings", "review_readability"),
        ("review_readability", "generate_faqs"),
        ("generate_faqs", "optimize_draft"),
        ("optimize_draft", "run_risk_checks"),
        ("run_risk_checks", "score_output"),
        ("score_output", "assemble_package"),
    )
    graph.add_conditional_edges(
        "intake_validate",
        route_after_intake,
        {"normalize_input": "normalize_input", "assemble_package": "assemble_package"},
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
