"""finalize node — assemble the terminal BlogPackage (DESIGN §1.2, §7).

Seventh repair pass:
- Removed plan_title kwarg from tel.log("finalize.enrich.derived"): generated content
  must not flow through telemetry (plan.title is LLM-derived content).
- _fallback_enrichment: prefers BlogPlan.target_keywords for SEO keywords (seventh repair
  schema addition) rather than always deriving from section headings.

Sixth repair pass (intact):
- Issue #1 / #6 (Enrichment bypasses cost ceiling + finalize violates graph contract):
  Removed the LLM call from finalize entirely.  DESIGN defines finalize as a non-billable
  assembly node.  Enrichment is now always derived from already-generated typed plan/draft
  data via _fallback_enrichment — zero cost, no telemetry needed, no injection risk, and
  the cost ceiling can never be breached by enrichment.

Fifth repair pass (intact):
- Issue #3 (Accumulated flags): finalize uses () for hard_fail_flags on 'pass' packages
  instead of the accumulated state["hard_fail_flags"].
- status 'passed' renamed to 'pass'.
- _determine_status receives actual_spend+ceiling_inr to detect post-draft ceiling exceeded.
- Error path: only sanitized node/kind info exposed; raw exception text never stored.
"""
from __future__ import annotations
from typing import Any
from core.cost import total_cost_inr
from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from ..schemas import (
    BlogEnrichment, BlogPackage, BlogPlan, CostUsage,
    ExtractedIdeas, QualityReport, StageCost,
)
from ..state import BlogState


def make_finalize_node(cfg: dict, llm: LLMProvider, tel: Telemetry):
    # llm is kept in the signature for interface consistency with all other node factories.
    # Finalize is a non-billable assembly node and does NOT invoke the LLM (sixth repair).
    _ = llm  # intentionally unused; future enrichment node will use a gated graph stage
    ceiling_inr: float = float(cfg.get("cost", {}).get("ceiling_inr", 50.0))

    def finalize(state: BlogState) -> dict[str, Any]:
        # ── Cost ledger (always computed first) ──────────────────────────────
        stage_costs: list[StageCost] = list(state.get("cost_usage", []))  # type: ignore[assignment]
        total_inr = round(total_cost_inr(stage_costs), 6)

        # ── Error-state path ──────────────────────────────────────────────────
        error_state: dict | None = state.get("error_state")  # type: ignore[assignment]
        if error_state:
            node_name = error_state.get("node", "unknown")
            kind = error_state.get("kind", "Error")
            # message is safe: either set explicitly by nodes (intake, cost_gate) with
            # a deliberately non-sensitive string, or sanitized by _node_with_error_guard
            # to just the exception type name — raw exception text is never stored.
            err_msg = error_state.get("message", kind)
            notes = f"Error in {node_name} ({kind}): {err_msg}"
            cost_obj = CostUsage(stage_costs=tuple(stage_costs), total_inr=total_inr)
            pkg = BlogPackage(
                status="error",
                cost=cost_obj,
                notes=notes,
                hard_fail_flags=tuple(state.get("hard_fail_flags", [])),  # type: ignore[arg-type]
            )
            with tel.span("finalize") as span_id:
                tel.log("finalize.complete", span_id=span_id, status="error")
            return {"final_output": pkg}

        # ── Normal terminal path ──────────────────────────────────────────────
        extracted_ideas: ExtractedIdeas | None = state.get("extracted_ideas")  # type: ignore[assignment]
        blog_plan: BlogPlan | None = state.get("blog_plan")  # type: ignore[assignment]
        quality: QualityReport | None = state.get("quality")  # type: ignore[assignment]
        draft: str | None = state.get("draft")  # type: ignore[assignment]
        revision_count: int = state.get("revision_count", 0)  # type: ignore[assignment]
        accumulated_flags: list[str] = state.get("hard_fail_flags", [])  # type: ignore[assignment]
        cost_gate_ok: bool = state.get("cost_gate_ok", True)  # type: ignore[assignment]
        max_cycles: int = cfg.get("graph", {}).get("max_revision_cycles", 2)

        status, notes = _determine_status(
            cost_gate_ok=cost_gate_ok,
            actual_spend=total_inr,
            ceiling_inr=ceiling_inr,
            extracted_ideas=extracted_ideas,
            quality=quality,
            revision_count=revision_count,
            max_cycles=max_cycles,
        )

        # ── Enrichment — derived from existing plan/draft data (sixth repair) ─
        # finalize is a non-billable assembly node; enrichment is derived from
        # already-generated typed plan/draft data (AGENT_SPEC §6.4).  No LLM call
        # is made here: zero cost, no telemetry required, no injection risk.
        # A dedicated gated graph stage can be added in a future increment if
        # LLM-quality enrichment metadata is needed.
        enrichment: BlogEnrichment | None = None
        if status == "pass":
            enrichment = _fallback_enrichment(blog_plan, draft)
            # Seventh repair: plan_title removed from telemetry — generated content
            # must not be logged through the telemetry system.
            tel.log("finalize.enrich.derived")

        # ── Cost object (no enrichment StageCost — enrichment is costless) ───
        cost_obj = CostUsage(stage_costs=tuple(stage_costs), total_inr=total_inr)

        # ── hard_fail_flags: never include accumulated history in a 'pass' package (Issue #3).
        # When quality.pass_flag=True the QualityReport invariant guarantees quality.hard_fail_flags=().
        # Accumulated state["hard_fail_flags"] can contain retriable flags from prior revision
        # cycles — including those in a 'pass' package causes _passed_package_invariants to raise.
        if status == "pass":
            final_flags: tuple[str, ...] = ()
        else:
            final_flags = tuple(accumulated_flags)

        improvement_suggestions: tuple[str, ...] = ()
        if quality and quality.improvement_suggestions:
            improvement_suggestions = quality.improvement_suggestions

        pkg = BlogPackage(
            status=status,
            title=blog_plan.title if blog_plan else None,
            full_draft=draft,
            source_notes=(
                tuple(extracted_ideas.source_notes)
                if extracted_ideas and extracted_ideas.source_notes else ()
            ),
            quality=quality,
            hard_fail_flags=final_flags,
            improvement_suggestions=improvement_suggestions,
            cost=cost_obj,
            notes=notes,
            revision_count=revision_count,
            # Enrichment fields — populated for 'pass', empty for other statuses
            alternative_titles=enrichment.alternative_titles if enrichment else (),
            short_summary=enrichment.short_summary if enrichment else None,
            seo_keywords=enrichment.seo_keywords if enrichment else (),
            suggested_tags=enrichment.suggested_tags if enrichment else (),
            meta_description=enrichment.meta_description if enrichment else None,
        )

        with tel.span("finalize") as span_id:
            tel.metric("total.cost_inr", total_inr, node="finalize")
            tel.log("finalize.complete", span_id=span_id, status=status,
                    revision_count=revision_count)

        return {"final_output": pkg}

    return finalize


def _determine_status(
    *,
    cost_gate_ok: bool,
    actual_spend: float,
    ceiling_inr: float,
    extracted_ideas: ExtractedIdeas | None,
    quality: QualityReport | None,
    revision_count: int,
    max_cycles: int,
) -> tuple[str, str | None]:
    """Determine the terminal BlogPackage status.

    Two cost-ceiling triggers:
    1. cost_gate_ok=False  — pre-draft gate blocked (cost_gate node or ceiling_exceeded node)
    2. actual_spend > ceiling_inr — post-draft actual spend exceeded ceiling
       (catches the case where draft cost exceeded its estimate AND
        route_after_draft routed to finalize without setting cost_gate_ok=False)
    """
    if not cost_gate_ok or actual_spend > ceiling_inr:
        return ("stopped_cost_ceiling", "Cost ceiling reached; run stopped to protect budget.")
    if extracted_ideas is not None and not extracted_ideas.usable:
        return ("needs_human", extracted_ideas.thin_reason or "Input too thin to draft a blog.")
    if quality is None:
        # Draft ran but review didn't — budget check in route_after_draft sent us here.
        return ("stopped_cost_ceiling", "Cost ceiling reached; review was not attempted.")
    if quality.hard_fail_flags:
        flags_str = ", ".join(quality.hard_fail_flags)
        return ("needs_human", f"Hard-fail flags raised: {flags_str}. Escalated to human review.")
    if quality.needs_human:
        return ("needs_human", quality.revision_notes or "Escalated to human review by quality checker.")
    if quality.pass_flag:
        return ("pass", None)
    return (
        "needs_human",
        (
            f"Quality score {quality.overall_score}/100 after {revision_count} revision(s); "
            "did not reach pass threshold. Review notes: "
            + (quality.revision_notes or "(none)")
        ),
    )


def _fallback_enrichment(blog_plan: BlogPlan | None, draft: str | None) -> BlogEnrichment:
    """Derive enrichment metadata from existing plan/draft when the LLM call fails.

    Guarantees non-empty values for all required fields so the fallback result
    always satisfies BlogEnrichment._required_fields_non_empty and
    BlogPackage._passed_package_invariants.
    """
    title = (blog_plan.title if blog_plan else None) or "Untitled Post"
    # Alternative title: simple reformulation of the main title
    alt_title = f"{title} — A Complete Guide"
    # Short summary: first complete prose sentence from the draft body, skipping
    # Markdown headings so the UI does not show "# Title ..." or mid-sentence text.
    summary = _derive_short_summary(title=title, draft=draft)
    # SEO keywords: prefer BlogPlan.target_keywords (seventh repair schema addition);
    # fall back to section headings if target_keywords is empty.
    if blog_plan and blog_plan.target_keywords:
        kw = blog_plan.target_keywords[:4]
    elif blog_plan and blog_plan.sections:
        sections = tuple(blog_plan.sections)
        kw_list = list(dict.fromkeys(s.lower() for s in sections))[:4]
        kw = tuple(kw_list) if kw_list else ("blog",)
    else:
        kw = ("blog",)
    # Suggested tags: subset of keywords
    tags = kw[:3]
    # Meta description: truncate summary to 160 chars
    meta = summary[:160].strip()
    if not meta:
        meta = f"Read about {title}."
    return BlogEnrichment(
        alternative_titles=(alt_title,),
        short_summary=summary[:500],
        seo_keywords=kw,
        suggested_tags=tags,
        meta_description=meta,
    )


def _derive_short_summary(*, title: str, draft: str | None) -> str:
    """Return a clean one-sentence summary derived from the draft body."""
    fallback = f"A blog post about {title}."
    raw = (draft or "").strip()
    if not raw:
        return fallback

    prose_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        prose_lines.append(stripped)

    prose = " ".join(" ".join(prose_lines).split())
    if not prose:
        return fallback

    # Prefer a complete sentence between 40 and 260 chars.
    for idx, ch in enumerate(prose):
        if ch in ".!?" and idx >= 40:
            return prose[: idx + 1].strip()

    if len(prose) <= 260:
        return prose

    clipped = prose[:260].rsplit(" ", 1)[0].rstrip(" ,;:")
    return (clipped or fallback).rstrip(".") + "."
