"""BlogState — the LangGraph graph state for Agent 01 (DESIGN §2).

Repair (Increment 3): renamed fields to match DESIGN.md; added error_state for
structured error routing through finalize; added placeholder fields.

Field renames
-------------
normalized_text  → normalized_content
plan             → blog_plan
draft_body       → draft
quality_report   → quality
revision_cycle   → revision_count  (semantics change: counts completed revisions only)
final_package    → final_output
error_context    → error_state
"""
from __future__ import annotations
import operator
from typing import Annotated, Any, TypedDict
from .schemas import Agent03BlogBrief, BlogPackage, BlogPlan, ExtractedIdeas, QualityReport, StageCost


class BlogState(TypedDict, total=False):
    # ---- input ------------------------------------------------------------------
    raw_input: str
    input_type: str               # "text" | "voice" | "video"
    writing_prefs: dict[str, Any] # unused placeholder in v1
    blog_brief_from_agent_03: Agent03BlogBrief

    # ---- media / transcription (Increment 6) ------------------------------------
    audio_ref: str                # set by extract_audio (video only); local path to WAV
    transcript: str               # set by transcribe (voice/video); raw STT text
    transcript_meta: dict[str, Any]  # provider/language/timestamps/duration/cost/latency

    # ---- intermediate artefacts -------------------------------------------------
    normalized_content: str       # was normalized_text
    extracted_ideas: ExtractedIdeas
    blog_plan: BlogPlan            # was plan
    draft: str                    # was draft_body

    # ---- review loop ------------------------------------------------------------
    quality: QualityReport         # was quality_report
    revision_count: int            # was revision_cycle; tracks completed REVISIONS not drafts

    # ---- accumulators (operator.add — never last-write-wins) --------------------
    hard_fail_flags: Annotated[list[str], operator.add]
    cost_usage: Annotated[list[StageCost], operator.add]

    # ---- cost-gate routing -------------------------------------------------------
    cost_gate_ok: bool

    # ---- error routing (routes to finalize when set) ----------------------------
    error_state: dict[str, Any]   # was error_context

    # ---- terminal ---------------------------------------------------------------
    status: str
    final_output: BlogPackage      # was final_package
