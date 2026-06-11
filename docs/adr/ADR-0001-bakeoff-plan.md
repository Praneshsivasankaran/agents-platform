# ADR-0001 Framework Bake-off — Execution Plan

**Date:** 2026-06-04
**Status:** Ready to execute (Sprint 0)
**Owner:** _[Human architect]_ (decision) · Claude Code (builds) · Codex (optional cross-check)
**Companion to:** ADR-0001 (framework selection). This plan **executes** ADR-0001's §"Decision method" and §"Reference agent". It does **not** itself decide the framework — it produces the evidence the architect records in ADR-0001's Decision/Consequences.

> Scope guard: this builds the **trivial reference agent only** — not the Blog Writing Agent. Agent 01's `DESIGN.md` is **not** part of this work; it comes after the framework is chosen.

---

## 1. Purpose & guardrails

- **Decides one thing:** which framework to standardize on — **LangGraph + LiteLLM + Pydantic** vs **Pydantic AI + LiteLLM** — for all ~40 agents. (ADK stays reference-only per ADR-0001; not built here.)
- **#1 criterion dominates:** provider/model agnosticism (weight 25). A framework that can't swap GCP → another provider by config alone, or that leaks a cloud SDK into `agent/`, loses regardless of other strengths.
- **Throwaway probe:** the reference agent is disposable. It exists to compare frameworks, not to become the golden agent.
- **Human-arbitrated:** Claude Code builds both tracks identically; the architect scores and decides; the rationale is recorded in ADR-0001.
- **Timebox it:** the logic is trivial — the effort is in the abstraction seam, not the agent. Resist creeping toward the blog pipeline.

---

## 2. Fair-comparison principle (shared substrate)

To make scores reflect the **framework** and not incidental scaffolding:

- Build **one identical, minimal slice** of `packages/core` and one identical set of schemas/tool/eval/Dockerfile/CI — used **byte-for-byte** by both tracks.
- Only the **framework wiring** (`agent/` + thin `providers/` glue + framework deps) differs between tracks.
- Record, per track, **how much glue** each framework needs to honor that shared substrate. That glue volume + friction is itself a primary signal.

This doubles as the first proof of the platform's abstraction seam.

---

## 3. The reference agent (identical for both tracks)

A trivial **"lookup + summarize"** agent, per ADR-0001:

- **Task:** accept a short query, call **one tool**, return a **structured** answer.
- **Tool:** `get_record(record_id: int) -> dict` — returns canned JSON from an in-memory map (e.g., `{"id": 42, "name": "...", "status": "active", "notes": "..."}`). Exercises tool/function-calling + permissioning (the tool is the agent's only "external" access).
- **Structured I/O (Pydantic):**
  - Input: `LookupQuery { query: str }`
  - Output: `LookupResult { record_id: int, summary: str, key_facts: list[str], source: str }`
- **State across 2 turns:** turn 1 "look up record 42"; turn 2 "what was its status again?" — the agent must remember the prior record/query without it being re-supplied. Exercises the state/memory model.
- **Model routing via LiteLLM (or equivalent), config-only swap:** a config key selects the model/provider; switching Vertex ↔ another provider (whatever keys you have) is a **config change only**, no code edit. The test is the *config-only swap*, not which providers.
- **One eval, wired pass/fail:** 1–2 JSON cases (query → a checkable property, e.g., `key_facts` contains the canned status, `record_id == 42`), a threshold (both cases pass), wired as a CI gate (non-zero exit on fail).
- **Observability:** at least one **trace span** around the run, one **structured JSON log** line, and one **token/cost metric** (from LiteLLM usage/cost). Cloud-neutral (OpenTelemetry + stdout JSON) — no LangSmith/Logfire dependency required to pass.
- **Containerized:** a `Dockerfile`; `docker run` executes the agent/eval locally; **no cloud-specific runtime**.
- **Agnosticism constraint (the real test):** everything under `agent/` imports **only the shared abstraction interfaces** — no `google.cloud.*`, `vertexai.*`, `boto3`, or `azure.*`. Framework imports (langgraph / pydantic-ai) are allowed; cloud SDKs are not. **Measure the friction each framework adds to honoring this.**

---

## 4. Shared, framework-neutral components (build once)

```
bakeoff/
  common/                         # identical across tracks
    core/
      llm_provider.py             # LLMProvider interface + LiteLLMProvider impl (config-selected model; emits token/cost)
      telemetry.py                # Telemetry interface + OTel/stdout impl (span, JSON log, cost metric)
      secret_store.py             # SecretStore interface + env-var stub (keys via env for the probe)
    schemas.py                    # LookupQuery, LookupResult
    tools/get_record.py           # canned-JSON stub tool (+ permission note)
    evals/cases.json              # 1–2 cases + threshold
    evals/test_reference.py       # pytest gate (pass/fail)
    checks/no_cloud_sdk.py        # AST/grep import guard run against each track's agent/
    config/base.yaml, gcp.yaml, alt.yaml   # provider/model selection
    Dockerfile                    # runs locally; no cloud runtime
    ci.yaml                       # lint + import-check + eval
  track-a-langgraph/  ...         # see §5
  track-b-pydantic-ai/ ...        # see §6
```

- **`no_cloud_sdk.py`:** walk `agent/` imports (AST) and fail on `google.cloud`, `vertexai`, `boto3`, `azure.*` (or a ruff/flake8 banned-import rule). This is the concrete form of ADR-0001's agnosticism test and the §9 agnostic-drift guard.
- **Config-only swap:** `base.yaml` sets `llm.provider`/`llm.model`; `gcp.yaml` and `alt.yaml` switch only those values. The eval runs against each with no code change.

---

## 5. Track A — LangGraph + LiteLLM + Pydantic

**Expected implementation shape**
- A `StateGraph` with a typed state (messages + looked-up record + final result).
- Nodes: a **model** node (calls the LLM via `core.LLMProvider`, may request the tool) → conditional edge → a **tool** node (`ToolNode` running `get_record`) → back to model → a **finalize** node producing `LookupResult` via structured output. (A prebuilt `create_react_agent` is an acceptable shortcut to evaluate too.)
- **2-turn state:** a LangGraph **checkpointer** (`MemorySaver` for the probe; pluggable to a real store later) keyed by a thread/session id.
- **Model seam:** the model node calls our `LLMProvider` (wrapping `litellm`); avoid importing LangChain's cloud provider integrations directly.
- **Structured output:** `with_structured_output(LookupResult)` or a Pydantic output parser.
- **Observability:** OTel callback + LiteLLM cost callback + JSON log (LangSmith optional, not required).

**Files/components Claude Code creates**
- `agent/state.py` (typed graph state)
- `agent/graph.py` (nodes, edges, conditional routing, checkpointer)
- `agent/nodes.py` (model + finalize nodes — import `core.LLMProvider`, `core.Telemetry`, `schemas`, `tools.get_record`)
- `providers/` (thin glue if `LLMProvider` must be adapted to a chat-model object)
- `pyproject.toml` (langgraph, langchain-core, litellm, pydantic, opentelemetry-* — **no** cloud provider extras)

**Pros**
- Explicit state graph fits branching/looping/multi-step naturally — matches the eventual blog pipeline + quality-escalation loop.
- First-class persistence (checkpointers) makes the 2-turn state clean.
- Mature, large ecosystem; many examples; strong tracing.
- Tools/`ToolNode` + structured output well-supported; multi-agent-capable (criterion #9).

**Cons**
- Heavier; more concepts (graph/nodes/edges/state/checkpointer) than a trivial agent needs.
- LangChain wants its own model abstraction; cleanly routing LiteLLM behind **our** `LLMProvider` (instead of using LangChain provider packages) can add a glue layer.
- Ecosystem churn / version drift; abstraction-over-abstraction can feel redundant.

**Friction points to watch**
- **LLM seam:** does `LLMProvider` cleanly feed LangGraph nodes, or do you end up using `ChatLiteLLM`/provider integrations directly (risking SDK leakage)? Measure glue.
- **SDK leakage:** some LangChain extras (e.g., `langchain-google-vertexai`) import `vertexai`/`google.cloud`. Keep them out of `agent/`; the import-check must pass.
- **Structured output** reliability across LiteLLM-routed models varies — note any per-model quirks.
- **Tracing lock-in:** confirm cloud-neutral OTel export works without LangSmith (touches criteria #2 and #6).

---

## 6. Track B — Pydantic AI + LiteLLM

**Expected implementation shape**
- A Pydantic AI `Agent` with a structured **output type** = `LookupResult` (native Pydantic structured output — verify the current API name, e.g., `output_type`/`result_type`), a system prompt, and a typed tool (`@agent.tool get_record`).
- **Model seam:** route via LiteLLM by either (a) pointing Pydantic AI's OpenAI-compatible model at a **LiteLLM proxy**, or (b) a small **custom Model adapter** delegating to our `core.LLMProvider`. The agent depends on our abstraction, not `litellm` directly.
- **2-turn state:** pass `message_history` from turn 1 into turn 2 (or keep a small session store). State is **app-owned**, not framework-managed.
- **Tool:** typed function tool, native.
- **Observability:** OTel + LiteLLM cost callback + JSON log (Logfire optional, not required).

**Files/components Claude Code creates**
- `agent/agent.py` (Pydantic AI `Agent`, output type, system prompt, `@agent.tool get_record` — imports `core.LLMProvider`, `core.Telemetry`, `schemas`)
- `agent/session.py` (2-turn state: message-history passing / session store)
- `providers/` (custom Model adapter over `LLMProvider`, or proxy config)
- `pyproject.toml` (pydantic-ai, litellm, pydantic, opentelemetry-* — Logfire only if used, prefer plain OTel)

**Pros**
- Lightweight, type-safe; **native** Pydantic structured output + typed tools → minimal glue for the I/O and tool criteria.
- Small surface; easy to fully wrap behind our abstractions; thin deps → clean golden template.
- Pairs naturally with our Pydantic schemas; low conceptual overhead for a trivial agent.

**Cons**
- Fewer orchestration batteries — you hand-build the 2-turn state plumbing and any future multi-step/branching/escalation graph. That glue is exactly what the golden template must provide to the other 39 if they're multi-step.
- Newer, smaller ecosystem; faster API churn; multi-agent (criterion #9) is more DIY.
- LiteLLM routing may be less first-class (proxy or custom adapter) — measure.

**Friction points to watch**
- **LiteLLM seam:** cleanest route (proxy vs custom Model)? Does provider-swap stay **config-only**? Measure glue.
- **State:** is the manual 2-turn memory clean, and does the pattern generalize to a multi-stage pipeline?
- **Observability lock-in:** ensure cloud-neutral OTel without a hard Logfire dependency (criteria #2, #6).
- **Maturity:** re-verify current API stability at bake-off time (ADR-0001 says re-verify capabilities at decision time).

---

## 7. Scoring approach (ADR-0001 criteria)

Score each framework **1–5 on evidence from the build**, not impressions. Weighted points = `score × weight ÷ 5`; total out of 100.

**Which criteria the build directly exercises (evidence-backed) vs judged from docs/ecosystem:**
- *Directly exercised:* #1 agnosticism (config-only swap + clean import-check), #3 deployment (containerized, runs off cloud), #4 tools (the one tool call), #5 state (2-turn memory), #6 observability (span/log/cost), #7 eval (eval-in-CI).
- *Judged from docs/ecosystem + how the build felt:* #2 license/lock-in, #8 maturity/community, #9 multi-agent support.

**Anchor for #1 (from ADR-0001):** 5 = provider by config only, one routing interface, no cloud SDK in agent, no cloud-bound deploy · 3 = agnostic with moderate glue · 1 = baked in.

**Per-finalist record (required, per ADR-0001):** lines of glue code; friction points; **was provider-swap truly config-only?**; eval-in-CI effort; subjective DX.

**Side-by-side scoresheet (fill after building):**

| # | Criterion | Weight | LangGraph (1–5) | →wtd | Pydantic AI (1–5) | →wtd |
|---|---|---:|:--:|:--:|:--:|:--:|
| 1 | Provider/model agnosticism | 25 | | | | |
| 2 | License & lock-in risk | 10 | | | | |
| 3 | Per-cloud deployment story | 10 | | | | |
| 4 | Tool / function-calling abstraction | 10 | | | | |
| 5 | State & memory model | 10 | | | | |
| 6 | Observability / tracing | 10 | | | | |
| 7 | Testing & eval support | 10 | | | | |
| 8 | Maturity & community | 8 | | | | |
| 9 | Multi-agent support | 7 | | | | |
| | **Weighted total (/100)** | **100** | | | | |

**Tie-break:** if totals are close, **criterion #1 decides**; then lower glue volume / better DX. Record the rationale either way.

---

## 8. Execution steps & timebox

1. **Build the shared substrate** (§4) once — core slice, schemas, tool, eval, import-check, Dockerfile, CI, config.
2. **Build Track A** (§5); capture the per-finalist record.
3. **Build Track B** (§6); capture the per-finalist record.
4. **Run both** through the same eval + import-check + `docker run`; collect the trace/log/cost output; perform the config-only provider swap on each.
5. **Score** both with the §7 matrix; **architect arbitrates**. (Optional: Codex reviews each build for SDK leakage / glue quality.)
6. **Record the decision** in ADR-0001 (§9) and standardize on the winner.

**Timebox:** ~1–2 days per track. The agent is trivial; budget the time for the abstraction seam, not the logic. Do not expand scope toward the blog pipeline.

---

## 9. Recommendation format — updating ADR-0001 after the bake-off

After scoring, update **ADR-0001** as follows (paste-ready):

**(a) Fill the scoring matrix** cells in ADR-0001 (scores + weighted totals for both candidates; ADK optional).

**(b) Decision section:**
```
- Chosen framework: <LangGraph + LiteLLM + Pydantic | Pydantic AI + LiteLLM>
- Why (tie to weighted scores + reference-agent experience): <agnosticism result, glue volume, config-only-swap outcome, DX, state/tracing fit>
- Runner-up and why not: <the gap that decided it>
- Conditions / exceptions: <e.g., a specific agent class allowed a second framework, or "none">
```

**(c) Consequences section:**
```
- What this locks in: <model-routing layer = LiteLLM confirmed; scaffold/CLI wiring to the chosen framework; CI checks incl. the no-cloud-SDK import guard; state/checkpoint pattern>
- What becomes harder / accepted trade-off: <e.g., heavier deps, or more orchestration glue to own>
- Follow-on ADRs triggered: <e.g., ADR-000X state/persistence backend; revisit ADR-0002 topology>
```

**(d) Flip status** `Proposed → Accepted`, date it, and confirm under "Related & pending decisions" that the **model-routing layer (LiteLLM)** is confirmed and **ADK remains reference-only**.

---

## 10. Notes

- **Re-verify framework capabilities and exact APIs at bake-off time** — both frameworks evolve; treat the API names above as indicative, not final (consistent with ADR-0001 and the §9 "stale assumptions" watch-item).
- The winner's wiring becomes the basis for the **scaffold CLI**, which then stamps out agent-01 (the blog agent) — built from the scaffold, never hand-rolled.
- Once the monorepo exists, this plan belongs alongside the decision at `docs/adr/` (e.g., `docs/adr/ADR-0001-bakeoff-plan.md`).
