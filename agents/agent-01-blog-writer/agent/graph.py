"""LangGraph StateGraph wiring for Agent 01 — Blog Writing Agent (DESIGN §1, §1.2).

Topology (Increment 6 — text + voice + video):

    intake
      |──text──────────────────────────────────────────────────→ normalize → ...
      |──voice────────────────────────────────────────────────→ transcribe → normalize → ...
      └──video──→ extract_audio → transcribe → normalize → ...

Shared spine from normalize onwards (all modalities):

    normalize → extract_ideas
                      |
               [route_after_extraction]
                usable=False ──────────────────────────────────────────+
                usable=True                                            |
                      |                                               |
                    plan                                              |
                      |                                               |
               [route_after_plan]                                     |
                gate_fails ────────────────────────────────────────+ |
                gate_ok                                             | |
                      |                                            | |
                    draft                                          | |
                      |                                            | |
               [route_after_draft]                                 | |
                error ─────────────────────────────────────────+ | |
                ceiling_exceeded → (sets ok=False) ────────────| | |
                ok                                             | | |
                      |                                        | | |
                   review                                      | | |
                      |                                        | | |
               [route_quality]                                 | | |
                pass/needs_human ─────────────────────────────|+| |
                terminal_hard_fail ─────────────────────────── |  |
                retriable_hard_fail → [cost_gate] (loop)       |  |
                revise → [cost_gate] ─────────────(loop)       |  |
                                                            finalize
                                                               |
                                                             END

Eighth repair pass (intact):
- route_after_draft and route_quality now check cost_gate_ok=False so that a
  CostCeilingExceeded raised inside draft or review routes to finalize, not review/cost_gate.

Seventh repair pass (intact):
- _node_with_error_guard distinguishes CostCeilingExceeded from unexpected exceptions.

Increment 6 additions:
- build_graph() now accepts an optional ``transcription`` TranscriptionProvider.
- New nodes: extract_audio, transcribe.
- route_after_intake now branches by input_type (text/voice/video).
- route_after_transcribe routes to normalize (both voice and video).
- route_after_extract_audio routes to transcribe on success, finalize on error.
- telemetry label registrations and dimension enums updated in base.yaml.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from core.cost import CostCeilingExceeded, estimate_for_stage, total_cost_inr, within_ceiling
from core.interfaces import LLMProvider, Telemetry
from core.interfaces.transcription import TranscriptionProvider
from .schemas import BillableNodeError as _BillableNodeError

# ---------------------------------------------------------------------------
# Error-guard wrapper
# ---------------------------------------------------------------------------


def _safe_billable_provider_category(exc: BaseException) -> str | None:
    """Return the content-free provider failure category carried by node wrappers.

    LLM nodes intentionally wrap BillableProviderError as RuntimeError with a
    fixed ``billable-provider-failure:<category>`` message.  That category is
    allowlisted by core.interfaces.errors and contains no prompt, response, or
    provider exception text, so it is safe to surface in the final package note.
    """
    msg = str(exc)
    prefix = "billable-provider-failure:"
    if not msg.startswith(prefix):
        return None
    category = msg[len(prefix):].split()[0].strip()
    return category or None


def _node_with_error_guard(
    node_name: str,
    node_fn: Callable,
    *,
    ceiling_inr: float = math.inf,
    tel: "Telemetry | None" = None,
) -> Callable:
    """Wrap a node function so exceptions are handled without crashing the graph.

    Four paths:
    - ``CostCeilingExceeded`` (pre-call rejection from authorize_call) → budget
      rejection signal.  Returns ``{"cost_gate_ok": False}`` → finalize produces
      stopped_cost_ceiling.  No provider call was made; no cost was incurred.
    - Post-call ceiling breach → the provider was called and actual cost exceeded the
      hard ceiling.  The incurred cost IS preserved in the returned state (tenth repair).
      ``cost_gate_ok=False`` stops downstream stages so no further spend accumulates.
    - ``BillableNodeError`` → post-response processing failed AFTER a successful LLM
      call.  The exception carries the incurred ``StageCost``; this guard appends it to
      ``cost_usage`` (honest ledger) while setting ``error_state`` so the run ends with
      status='error' (not stopped_cost_ceiling — an LLM call was made).
    - Any other ``Exception`` → unexpected error.  Returns ``error_state`` dict with a
      sanitized type name (no traceback, no raw message — those can contain file paths,
      local variable values, or secrets).
    """
    def guarded(state: dict) -> dict[str, Any]:
        try:
            result = node_fn(state)
            # ── Post-call ceiling check ────────────────────────────────────────
            new_costs = result.get("cost_usage")
            if new_costs and math.isfinite(ceiling_inr):
                prior = state.get("cost_usage") or []
                actual_total = total_cost_inr(list(prior) + list(new_costs))
                if actual_total > ceiling_inr:
                    return {**result, "cost_gate_ok": False}
            return result
        except CostCeilingExceeded:
            return {"cost_gate_ok": False}
        except _BillableNodeError as be:
            # Post-response processing failed.  The LLM was called and billed;
            # preserve the incurred cost in the ledger before recording the error.
            provider_category = _safe_billable_provider_category(be.cause)
            error_kind = "BillableProviderError" if provider_category else type(be.cause).__name__
            error_message = (
                f"Billable provider failure in {node_name}: {provider_category}"
                if provider_category
                else f"{type(be.cause).__name__} in {node_name}"
            )
            if tel is not None:
                try:
                    tel.log("node.error", node=node_name, kind=error_kind)
                except Exception:
                    pass  # telemetry failure must never hide the billing record
            return {
                "cost_usage": [be.stage_cost],
                "error_state": {
                    "node": node_name,
                    "kind": error_kind,
                    "message": error_message,
                },
            }
        except Exception as exc:
            if tel is not None:
                try:
                    tel.log("node.error", node=node_name, kind=type(exc).__name__)
                except Exception:
                    pass
            return {
                "error_state": {
                    "node": node_name,
                    "kind": type(exc).__name__,
                    # Deliberately omit raw str(exc) — it may contain sensitive data.
                    # Diagnostics are available in telemetry spans.
                    "message": f"{type(exc).__name__} in {node_name}",
                }
            }
    guarded.__name__ = f"guarded_{node_name}"
    return guarded


# ---------------------------------------------------------------------------
# Pure routing helpers (unit-testable without building the full graph)
# ---------------------------------------------------------------------------


def route_quality_decision(
    *,
    pass_flag: bool,
    needs_human: bool,
    hard_fail_flags: tuple,
    revision_cycle: int,
    max_cycles: int,
) -> str:
    """Return the next node name for the route_quality conditional edge.

    Rules (priority order):
    1. pass_flag=True                                       -> "finalize"
    2. needs_human=True                                     -> "finalize"
    3. Any TERMINAL hard_fail_flags                         -> "finalize"
    4. Any RETRIABLE hard_fail_flags + cycles exhausted     -> "finalize"
    5. Any RETRIABLE hard_fail_flags + cycles remaining     -> "cost_gate" (retry)
    6. revision_cycle >= max_cycles                         -> "finalize"
    7. Else (score too low, cycles remaining)               -> "cost_gate"
    """
    from .schemas import _TERMINAL_HARD_FAIL_CODES, _RETRIABLE_HARD_FAIL_CODES

    if pass_flag:
        return "finalize"
    if needs_human:
        return "finalize"
    # Terminal flags: always escalate — no retry possible
    terminal = [f for f in hard_fail_flags if f in _TERMINAL_HARD_FAIL_CODES]
    if terminal:
        return "finalize"
    # Retriable flags: attempt a revision if cycles remain
    retriable = [f for f in hard_fail_flags if f in _RETRIABLE_HARD_FAIL_CODES]
    if retriable:
        if revision_cycle >= max_cycles:
            return "finalize"
        return "cost_gate"
    # No hard-fail flags — plain low score
    if revision_cycle >= max_cycles:
        return "finalize"
    return "cost_gate"


from .nodes import (
    make_cost_gate_node,
    make_draft_node,
    make_extract_audio_node,
    make_extract_ideas_node,
    make_finalize_node,
    make_intake_node,
    make_normalize_node,
    make_plan_node,
    make_review_node,
    make_transcribe_node,
)
from .schemas import BlogPackage, CostUsage
from .state import BlogState


def _safe_finalize_wrapper(finalize_fn: Callable) -> Callable:
    """Last-resort guard around finalize.

    If finalize itself throws (e.g. a schema validator rejects a field combination, or
    telemetry crashes), this wrapper returns a minimal BlogPackage so graph.invoke()
    always returns a structured result.

    Preserves actual spend: reporting ₹0 during a finalize failure misrepresents the
    true ledger during exactly the failure path where accurate accounting matters most.
    """
    def safe_finalize(state: dict) -> dict[str, Any]:
        try:
            return finalize_fn(state)
        except Exception as exc:
            # Preserve actual spend recorded before finalize failed.
            try:
                stage_costs = state.get("cost_usage", [])
                actual_total = round(total_cost_inr(stage_costs), 6)
                cost_obj = CostUsage(stage_costs=tuple(stage_costs), total_inr=actual_total)
            except Exception:
                cost_obj = CostUsage(stage_costs=(), total_inr=0.0)
            pkg = BlogPackage(
                status="error",
                cost=cost_obj,
                # Do NOT surface raw exception text — it may contain sensitive data.
                notes=f"Fatal error in finalize ({type(exc).__name__}): internal error",
                hard_fail_flags=(),
            )
            return {"final_output": pkg}
    safe_finalize.__name__ = "safe_finalize"
    return safe_finalize


def build_graph(
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    transcription: TranscriptionProvider | None = None,
) -> Any:
    """Compile and return the Agent 01 LangGraph CompiledStateGraph.

    Parameters
    ----------
    cfg:
        Agent configuration dict (base.yaml or cloud overlay).
    llm:
        LLMProvider instance (mock or real).
    tel:
        Telemetry instance.
    transcription:
        TranscriptionProvider instance (required for voice/video inputs).
        Defaults to ``None``; voice/video runs will raise at node-build time if absent.

    Returns
    -------
    A compiled LangGraph graph.  Invoke with::

        result = graph.invoke({"raw_input": "...", "input_type": "text"})
        package = result["final_output"]
    """
    from core.factory import get_transcription_provider

    # If no transcription provider is passed, build one from config.
    # For text-only runs this provider is constructed but never called.
    if transcription is None:
        transcription = get_transcription_provider(cfg)

    max_cycles: int = cfg.get("graph", {}).get("max_revision_cycles", 2)
    cost_cfg: dict = cfg.get("cost", {})
    ceiling_inr: float = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs: dict[str, float] = {
        k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()
    }

    # ---- Node instances -------------------------------------------------------
    intake_node         = _node_with_error_guard("intake",        make_intake_node(cfg, llm, tel),                                tel=tel)
    extract_audio_node  = _node_with_error_guard("extract_audio", make_extract_audio_node(cfg, llm, tel),                         tel=tel)
    transcribe_node     = _node_with_error_guard("transcribe",    make_transcribe_node(cfg, llm, tel, transcription),             ceiling_inr=ceiling_inr, tel=tel)
    normalize_node      = _node_with_error_guard("normalize",     make_normalize_node(cfg, llm, tel),                            ceiling_inr=ceiling_inr, tel=tel)
    extract_node        = _node_with_error_guard("extract_ideas", make_extract_ideas_node(cfg, llm, tel),                        ceiling_inr=ceiling_inr, tel=tel)
    plan_node           = _node_with_error_guard("plan",          make_plan_node(cfg, llm, tel),                                 ceiling_inr=ceiling_inr, tel=tel)
    cost_gate_node      = _node_with_error_guard("cost_gate",     make_cost_gate_node(cfg, llm, tel),                            tel=tel)
    draft_node          = _node_with_error_guard("draft",         make_draft_node(cfg, llm, tel),                                ceiling_inr=ceiling_inr, tel=tel)
    review_node         = _node_with_error_guard("review",        make_review_node(cfg, llm, tel),                               ceiling_inr=ceiling_inr, tel=tel)
    finalize_node       = _safe_finalize_wrapper(make_finalize_node(cfg, llm, tel))

    # ---- Thin sentinel node — records that ceiling was exceeded post-draft ----
    def ceiling_exceeded_node(state: dict) -> dict[str, Any]:
        """Set cost_gate_ok=False so finalize returns stopped_cost_ceiling status."""
        return {"cost_gate_ok": False}

    # ---- Route.decision telemetry helper -----------------------------------

    def _emit_route(node: str, decision: str, target: str) -> None:
        """Emit a route.decision event; swallow telemetry errors (routing must not fail)."""
        try:
            tel.log("route.decision", node=node, decision=decision, target=target)
        except Exception:
            pass

    # ---- Conditional edge functions ------------------------------------------

    def route_after_intake(state: BlogState) -> str:
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("intake", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("intake", "cost_ceiling", "finalize")
            return "finalize"
        input_type: str = state.get("input_type", "text") or "text"  # type: ignore[attr-defined]
        if input_type == "voice":
            _emit_route("intake", "ok", "transcribe")
            return "transcribe"
        if input_type == "video":
            _emit_route("intake", "ok", "extract_audio")
            return "extract_audio"
        # text (default)
        _emit_route("intake", "ok", "normalize")
        return "normalize"

    def route_after_extract_audio(state: BlogState) -> str:
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("extract_audio", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("extract_audio", "cost_ceiling", "finalize")
            return "finalize"
        _emit_route("extract_audio", "ok", "transcribe")
        return "transcribe"

    def route_after_transcribe(state: BlogState) -> str:
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("transcribe", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("transcribe", "cost_ceiling", "finalize")
            return "finalize"
        _emit_route("transcribe", "ok", "normalize")
        return "normalize"

    def route_after_normalize(state: BlogState) -> str:
        """Error or CostCeilingExceeded in normalize → skip billable nodes → finalize."""
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("normalize", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("normalize", "cost_ceiling", "finalize")
            return "finalize"
        _emit_route("normalize", "ok", "extract_ideas")
        return "extract_ideas"

    def route_after_extraction(state: BlogState) -> str:
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("extract_ideas", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("extract_ideas", "cost_ceiling", "finalize")
            return "finalize"
        extracted = state.get("extracted_ideas")  # type: ignore[attr-defined]
        if extracted is not None and not extracted.usable:
            _emit_route("extract_ideas", "usable_false", "finalize")
            return "finalize"
        _emit_route("extract_ideas", "ok", "plan")
        return "plan"

    def route_after_plan(state: BlogState) -> str:
        """Error or CostCeilingExceeded in plan → finalize.  Otherwise → cost_gate."""
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("plan", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("plan", "cost_ceiling", "finalize")
            return "finalize"
        _emit_route("plan", "ok", "cost_gate")
        return "cost_gate"

    def route_after_cost_gate(state: BlogState) -> str:
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("cost_gate", "error", "finalize")
            return "finalize"
        ok: bool = state.get("cost_gate_ok", True)  # type: ignore[attr-defined]
        if ok:
            _emit_route("cost_gate", "ok", "draft")
            return "draft"
        _emit_route("cost_gate", "cost_ceiling", "finalize")
        return "finalize"

    def route_after_draft(state: BlogState) -> str:
        """Error or budget rejection in draft → finalize.  Post-draft → ceiling_exceeded or review."""
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("draft", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("draft", "cost_ceiling", "finalize")
            return "finalize"
        try:
            stage_costs = state.get("cost_usage", [])
            current = total_cost_inr(stage_costs)
            if current > ceiling_inr:
                _emit_route("draft", "cost_ceiling", "ceiling_exceeded")
                return "ceiling_exceeded"
            review_est = estimate_for_stage("review", estimated_costs)
            if not within_ceiling(current, review_est, ceiling_inr=ceiling_inr):
                _emit_route("draft", "cost_ceiling", "ceiling_exceeded")
                return "ceiling_exceeded"
        except (ValueError, KeyError):
            _emit_route("draft", "error", "finalize")
            return "finalize"
        _emit_route("draft", "ok", "review")
        return "review"

    def route_quality(state: BlogState) -> str:
        """Route after review.  Error or budget rejection → finalize.  Otherwise quality decision."""
        if state.get("error_state") is not None:  # type: ignore[attr-defined]
            _emit_route("review", "error", "finalize")
            return "finalize"
        if not state.get("cost_gate_ok", True):  # type: ignore[attr-defined]
            _emit_route("review", "cost_ceiling", "finalize")
            return "finalize"
        report = state.get("quality")  # type: ignore[attr-defined]
        revision_count: int = state.get("revision_count", 0)  # type: ignore[attr-defined]
        if report is None:
            _emit_route("review", "error", "finalize")
            return "finalize"
        decision = route_quality_decision(
            pass_flag=report.pass_flag,
            needs_human=report.needs_human,
            hard_fail_flags=report.hard_fail_flags,
            revision_cycle=revision_count,
            max_cycles=max_cycles,
        )
        # Map outcome to sanitized telemetry value.
        if decision == "finalize":
            if report.pass_flag:
                _emit_route("review", "pass", "finalize")
            elif report.needs_human:
                _emit_route("review", "needs_human", "finalize")
            else:
                _emit_route("review", "terminal_hard_fail", "finalize")
        else:
            _emit_route("review", "revise", "cost_gate")
        return decision

    # ---- Graph construction --------------------------------------------------
    graph = StateGraph(BlogState)

    graph.add_node("intake",        intake_node)
    graph.add_node("extract_audio", extract_audio_node)
    graph.add_node("transcribe",    transcribe_node)
    graph.add_node("normalize",     normalize_node)
    graph.add_node("extract_ideas", extract_node)
    graph.add_node("plan",          plan_node)
    graph.add_node("cost_gate",     cost_gate_node)
    graph.add_node("draft",         draft_node)
    graph.add_node("review",        review_node)
    graph.add_node("finalize",      finalize_node)
    graph.add_node("ceiling_exceeded", ceiling_exceeded_node)

    graph.set_entry_point("intake")

    # ---- Media path edges -------------------------------------------------------
    graph.add_conditional_edges(
        "intake", route_after_intake,
        {"finalize": "finalize", "normalize": "normalize",
         "transcribe": "transcribe", "extract_audio": "extract_audio"},
    )
    graph.add_conditional_edges(
        "extract_audio", route_after_extract_audio,
        {"finalize": "finalize", "transcribe": "transcribe"},
    )
    graph.add_conditional_edges(
        "transcribe", route_after_transcribe,
        {"finalize": "finalize", "normalize": "normalize"},
    )

    # ---- Shared spine edges (text + post-transcription) -------------------------
    graph.add_conditional_edges(
        "normalize", route_after_normalize,
        {"finalize": "finalize", "extract_ideas": "extract_ideas"},
    )
    graph.add_conditional_edges(
        "extract_ideas", route_after_extraction,
        {"finalize": "finalize", "plan": "plan"},
    )
    graph.add_conditional_edges(
        "plan", route_after_plan,
        {"finalize": "finalize", "cost_gate": "cost_gate"},
    )
    graph.add_conditional_edges(
        "cost_gate", route_after_cost_gate,
        {"draft": "draft", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "draft", route_after_draft,
        {"finalize": "finalize", "review": "review", "ceiling_exceeded": "ceiling_exceeded"},
    )
    graph.add_edge("ceiling_exceeded", "finalize")
    graph.add_conditional_edges(
        "review", route_quality,
        {"finalize": "finalize", "cost_gate": "cost_gate"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()
