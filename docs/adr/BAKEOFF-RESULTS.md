> **⚠️ HISTORICAL — bake-off evidence.** This document is the historical record of the framework
> bake-off. **ADR-0001 is now Accepted** (framework = LangGraph + LiteLLM + Pydantic). The live
> Vertex/LiteLLM smoke test and the independent Codex implementation review remain **pending before
> final implementation/merge** (not complete). Any wording below implying ADR-0001 must *not* be
> accepted yet — or that `DESIGN.md` must not be started — is **historical and superseded by
> ADR-0001** (`docs/adr/ADR-0001-framework-selection.md`).

# Framework Bake-Off — Results & Decision Evidence (ADR-0001)

**Scope:** Choose the platform agent framework using the throwaway *lookup-and-summarize* reference agent defined in the ADR-0001 bake-off plan. This document is **framework-decision evidence only**. The Blog Writing Agent `DESIGN.md` is deliberately **not** started; it comes after ADR-0001 is accepted.

**Tracks compared**
- **Track A — LangGraph + LiteLLM + Pydantic**
- **Track B — Pydantic AI + LiteLLM**
- (ADK remained reference-only, per the plan — not built.)

**Fair-comparison rule held:** the abstraction layer (the `packages/core` slice — `LLMProvider`, `Telemetry`, `SecretStore`, shared Pydantic schemas, the canned `get_record` tool, the eval cases, the `no_cloud_sdk` check, config, Dockerfile/CI) was built **once** and shared verbatim by both tracks. Only the framework varied.

---

## 0. Honesty caveats (read first)

1. **No live model calls.** The sandbox has no provider keys and no network to Vertex/OpenAI/Anthropic, so **every track was validated with a deterministic offline model**, not a real LLM. This is acceptable because **none of the nine ADR-0001 criteria is "model output quality"** — they are all about wiring, abstraction, agnosticism, state, observability, testing, deploy, maturity, and multi-agent fit, all of which are exercised offline. **A live smoke test on real Vertex (GCP-first) via LiteLLM is still required before ratifying** — see Section 7.
2. **The "Codex review" here is a self-review.** Claude implemented the tracks, so Section 4 is a self-review *written in the Codex checklist format*, not an independent second-model pass. **A real Codex cross-verification pass remains the architect's to run** before flipping ADR-0001 to Accepted. This preserves the playbook's Claude-implements / Codex-verifies separation.
3. **Synthetic cost/usage.** Token counts and `cost_usd` in telemetry are synthetic constants flagged `"synthetic": true`; they prove the metric path, not real spend.

---

## 1. What was built

```
bakeoff/
├── common/                         # shared, framework-neutral substrate (built once)
│   ├── core/
│   │   ├── llm.py                  # LLMProvider ABC + MockLLMProvider (offline) + LiteLLMProvider (prod, lazy) + get_provider(cfg)
│   │   ├── telemetry.py            # Telemetry: cloud-neutral JSON spans/logs/metrics (OTel in prod)
│   │   └── secret_store.py         # SecretStore ABC + EnvSecretStore stub
│   ├── schemas.py                  # LookupQuery, LookupResult (shared Pydantic I/O contract)
│   ├── tools/get_record.py         # canned tool + CALLS counter (proves turn-2 used memory)
│   ├── evals/
│   │   ├── cases.json              # 2 cases: lookup_active, recall_status_from_memory
│   │   └── asserts.py              # check_case(case, results) -> (passed, reasons)
│   ├── checks/no_cloud_sdk.py      # AST import scan; bans google.cloud / vertexai / boto3 / botocore / azure
│   ├── config/{base,gcp,alt}.yaml  # base=mock(offline), gcp=litellm/vertex, alt=litellm/anthropic
│   ├── Dockerfile                  # python:3.12-slim + ffmpeg + requirements
│   └── ci.yaml                     # GitHub Actions: install -> no_cloud_sdk -> pytest per track
│
├── track-a-langgraph/
│   ├── agent/state.py              # AgentState TypedDict (message-accumulating channel + record slot)
│   ├── agent/graph.py              # StateGraph: model_node / tool_node / conditional route + MemorySaver checkpointer
│   ├── providers/model.py          # thin: returns get_provider(cfg)
│   ├── app.py                      # make(), run_turn(), CLI (swap table + 2-turn demo)
│   ├── tests/test_reference.py     # runs shared cases.json via check_case
│   └── requirements.txt
│
└── track-b-pydantic-ai/
    ├── agent/agent.py              # Pydantic AI Agent(output_type=str) + get_record tool (closure over Telemetry)
    ├── agent/offline_model.py      # scripted FunctionModel mirroring MockLLMProvider (offline test double)
    ├── agent/cache.py              # LAST_RECORD slot (analogue of Track A's state["record"])
    ├── providers/model.py          # mock/test -> FunctionModel; litellm -> OpenAI-compat -> LiteLLM proxy (lazy, prod)
    ├── app.py                      # make(), run_turn() (threads message_history), CLI (swap table + 2-turn demo)
    ├── tests/test_reference.py     # same shared cases + 1 native typed-output test (TestModel)
    └── requirements.txt
```

Versions exercised: **LangGraph 1.2.4**, **langchain-core 1.4.0**, **Pydantic AI 1.105.0**, **pydantic 2.13.4**, Python 3.12. Each track ran in its own venv to avoid dependency cross-talk.

---

## 2. What executed and the results

| Check (identical for both) | Track A — LangGraph | Track B — Pydantic AI |
|---|---|---|
| `no_cloud_sdk` import scan (agent + providers) | **PASS** (no banned imports) | **PASS** (no banned imports) |
| Shared eval `cases.json` via `check_case` | **2/2 PASS** | **2/2 PASS** (+1 native typed-output test = **3 passed**) |
| Config-only provider/model swap (base→gcp→alt) | **Yes** — `mock → litellm(vertex) → litellm(anthropic)`, **zero agent-code change** | **Yes** — `mock(FunctionModel) → OpenAI-compat→LiteLLM(vertex/anthropic)`, **zero agent-code change** |
| 2-turn memory (turn-2 answers without re-calling the tool) | **Yes** — `CALLS` stayed at 1 across recall (MemorySaver checkpointer) | **Yes** — `CALLS` stayed at 1 across recall (threaded `message_history`) |
| Trace / log / token-cost metric (shared `Telemetry`) | **Yes** — per-node `span_start/span_end`, `model.tool_call`/`tool.result` logs, `llm.cost_usd` metric | **Yes** — `tool` span + run-level span, `tool.result` log, `llm.cost_usd` metric |
| Local run (`python app.py`) | **Yes** | **Yes** |
| Docker image build | **Not run** — no Docker daemon in sandbox; Dockerfile + CI provided, build **deferred to CI** | same |

> Both eval suites validate **wiring**, not model quality. The shared eval is apples-to-apples: turn 1 calls the tool and yields a typed `LookupResult` (record_id + "active"); turn 2 recalls "blocked" from memory with no new tool call. Both tracks satisfy it identically.

**Observability — Track A sample (one lookup turn, abridged):**
```json
{"event":"span_start","span":"model","node":"model","trace_id":"…"}
{"event":"metric","name":"llm.cost_usd","value":0.0016,"synthetic":true,"trace_id":"…"}
{"event":"span_end","span":"model","duration_ms":0.21,"trace_id":"…"}
{"event":"log","msg":"model.tool_call","tool":"get_record","args":{"record_id":42},"trace_id":"…"}
{"event":"span_start","span":"tool","tool":"get_record","trace_id":"…"}
{"event":"log","msg":"tool.result","record_id":42,"status":"active","trace_id":"…"}
{"event":"span_end","span":"tool","duration_ms":0.03,"trace_id":"…"}
```
**Track B sample (same turn):** identical `Telemetry` schema; emits the `tool` span + `tool.result` log + (in `run_turn`) a run-level span and the synthetic `llm.cost_usd` metric. The difference is **granularity**: Track A's explicit nodes yield per-model-step spans "for free"; Track B's model step is internal to the framework, so model-step granularity needs the run-level wrapper (or bridging Pydantic AI's own OTel/Logfire instrumentation).

---

## 3. Per-track findings

| Dimension | Track A — LangGraph | Track B — Pydantic AI |
|---|---|---|
| **Glue code (code lines, ex-comments/blank)** | ~111 (state + graph + providers + app). Offline test double = **0 track lines** (reuses shared `MockLLMProvider` through the `LLMProvider` seam). | ~101 production (cache + agent + providers + app) — slightly leaner because the framework runs the tool loop. **+34 lines** for a framework-specific offline double (`FunctionModel`). |
| **Friction points** | Hand-wire the loop: `model_node` / `tool_node` / conditional `route` / `START`/`END` edges; translate `LLMResponse` ↔ message dicts; pick the checkpointer. More moving parts, but explicit and inspectable. | Pydantic AI API is **version-volatile** (1.105.0): had to introspect `FunctionModel`/`AgentInfo`, `ModelResponse`/`ToolCallPart`/`ToolReturnPart`, and the result accessor (`result.output`) before coding. Reaching **LiteLLM** is indirect (OpenAI-compatible endpoint/proxy), not a direct SDK call. |
| **Provider/model swap truly config-only?** | **Yes.** Single seam: `get_provider(cfg)`. No `agent/` change across mock/vertex/anthropic. | **Yes.** Single seam: `get_model(cfg)`. No `agent/` change. (Production adds one hop: agent → OpenAI-compat → LiteLLM.) |
| **Eval-in-CI effort** | Low. Plain pytest over shared `cases.json`; shared `MockLLMProvider` drives deterministic runs with no framework-specific scaffolding. | Low–medium. Pydantic AI ships **first-class testing primitives** (`TestModel`, `FunctionModel`) — a real plus — but deterministic *content* required scripting a `FunctionModel`; `TestModel` alone fabricates field values and re-calls tools (fine for type/shape, not content/recall). |
| **Observability effort** | Low. Explicit nodes = natural per-step span boundaries with the shared `Telemetry`. | Low for tool spans (closure over `Telemetry`); **medium** for model-step granularity (loop is internal — wrap at run level or bridge OTel/Logfire). |
| **Structured (Pydantic) I/O** | Built in app/node code from the tool result (framework doesn't own it). Same `LookupResult` contract. | **Native**: `output_type=LookupResult` validated by the framework's output tool (separately proven via `TestModel`). Headline strength. |
| **Developer experience (subjective)** | Verbose but predictable and transparent; the graph topology *is* the control flow, which pays off as flows get multi-step. | Terse and ergonomic for a single agent + tools + typed output; less ceremony — but more version surprises and an extra seam to route LiteLLM. |
| **Cloud / vendor leakage risk** | **Low.** No cloud SDK in `agent/`; model access only via `LLMProvider`→LiteLLM. `no_cloud_sdk` PASS. | **Low.** No cloud SDK in `agent/`; production routes through LiteLLM via an OpenAI-compatible interface. `no_cloud_sdk` PASS. |

---

## 4. Codex-format self-review (NOT an independent Codex pass — see caveat #2)

Format mirrors the §8.3 Codex checklist. Each line is a self-assessment to be **confirmed by a real Codex run**.

### Track A — LangGraph
- **Cloud SDK leakage:** PASS — `agent/` and `providers/` import only `langgraph`, `langchain-core`, `pydantic`, stdlib, and shared `common.*`. No `google.cloud`/`vertexai`/`boto3`/`azure`. Verified by `no_cloud_sdk`.
- **Agnostic abstraction quality:** STRONG — the node depends on the generic `LLMProvider`; the framework never sees a vendor. Swapping providers is a config edit.
- **Config-only swap validity:** VALID — single resolution point (`get_provider`); demonstrated across 3 configs with no `agent/` diff.
- **Glue quality:** ACCEPTABLE — explicit `model_node`/`tool_node`/`route` is boilerplate but clear; should be **generated by the scaffold** so 40 agents don't re-hand-write it.
- **Eval/observability correctness:** PASS — eval asserts real tool-call + typed result + memory recall; telemetry emits structured spans/logs/metrics with a trace id. Cost is synthetic (flagged).
- **Self-review flags:** message dicts are hand-rolled (OpenAI-ish shape); confirm they map cleanly onto LiteLLM's expected schema on the live path.

### Track B — Pydantic AI
- **Cloud SDK leakage:** PASS — imports only `pydantic_ai`, `pydantic`, stdlib, shared `common.*`; the production branch lazily imports `pydantic_ai.models.openai` (not a cloud SDK) and is never executed offline. Verified by `no_cloud_sdk`.
- **Agnostic abstraction quality:** STRONG, with a caveat — genuinely vendor-neutral, but reaching LiteLLM goes through an OpenAI-compatible hop rather than a direct provider call, so there is **more integration surface** to keep neutral.
- **Config-only swap validity:** VALID — single resolution point (`get_model`); demonstrated across 3 configs with no `agent/` diff.
- **Glue quality:** GOOD for production (framework runs the loop), but the **offline test double is framework-specific** (`FunctionModel`, +34 lines) where Track A reused the shared `Mock` for free.
- **Eval/observability correctness:** PASS — same shared eval passes; native typed output independently proven via `TestModel`; tool spans are clean. Model-step spans require the run-level wrapper (loop is internal).
- **Self-review flags:** version volatility (1.105.0) means the offline `FunctionModel` and result accessors are version-sensitive; pin `pydantic-ai` and re-verify on upgrade. Confirm the OpenAI-compat→LiteLLM path on the live smoke test.

---

## 5. Filled ADR-0001 scoring matrix

Weighting and criteria are exactly as fixed in ADR-0001. **Weighted = raw(/5) × weight ÷ 5.**

| # | Criterion | Weight | LangGraph raw | LangGraph wtd | Pydantic AI raw | Pydantic AI wtd | Evidence basis |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | Provider/model agnosticism | 25 | 5 | **25.0** | 5 | **25.0** | Both vendor-neutral; both passed config-only swap + `no_cloud_sdk`. (Texture differs — see note.) |
| 2 | License / lock-in | 10 | 4 | **8.0** | 5 | **10.0** | Both permissive OSS. Pydantic AI lighter footprint; LangGraph pulls langchain-core + more gravity. |
| 3 | Deployment / container | 10 | 5 | **10.0** | 5 | **10.0** | Identical slim+ffmpeg Dockerfile & CI work for both; local run clean. |
| 4 | Tool / function calling | 10 | 4 | **8.0** | 5 | **10.0** | Pydantic AI: decorator tool + auto-schema + framework-run loop. LangGraph: hand-wired tool node + schema. |
| 5 | State / memory | 10 | 5 | **10.0** | 3 | **6.0** | LangGraph: native `MemorySaver` checkpointer by thread_id. Pydantic AI: app-owned `message_history`. |
| 6 | Observability | 10 | 4 | **8.0** | 4 | **8.0** | Same `Telemetry`; LangGraph finer per-node spans for free, Pydantic AI native OTel/Logfire — net even. |
| 7 | Testing / eval | 10 | 4 | **8.0** | 5 | **10.0** | Pydantic AI ships `TestModel`/`FunctionModel` first-class. LangGraph reuses shared Mock (easy, no primitives). |
| 8 | Maturity / ecosystem | 8 | 5 | **8.0** | 3 | **4.8** | LangGraph older, widely deployed, large community; Pydantic AI capable but younger. |
| 9 | Multi-agent readiness | 7 | 5 | **7.0** | 3 | **4.2** | LangGraph built for multi-node/multi-agent graphs; Pydantic AI more single-agent-centric. |
| | **TOTAL** | **100** | | **92.0** | | **88.0** | |

**Note on #1 (both = 5):** both frameworks are truly agnostic, so neither is docked. The real difference is *integration surface*: Track A's node calls the generic `LLMProvider` directly (zero bridge), while Track B reaches LiteLLM through an OpenAI-compatible hop (one extra seam). That texture is captured in #2/#4/DX, not as an agnosticism penalty.

**Grounding:** criteria #1, #3, #4, #5, #6, #7 are scored from the **actual build/run evidence** above; #2, #8, #9 are ecosystem/longevity judgments. Live model quality is intentionally **not** a criterion — that belongs to the Blog Writing Agent's own eval, not the framework bake-off.

---

## 6. Recommendation

**Adopt Track A — LangGraph + LiteLLM + Pydantic — as the platform agent framework.** (92 vs 88.)

**Why it wins.** The tie-break in ADR-0001 says #1 (agnosticism) dominates, then glue/DX. #1 is **tied at 5/5**, so the decision falls to the platform-longevity dimensions, where LangGraph leads decisively: **state/memory (10 vs 6), maturity (8 vs 4.8), and multi-agent readiness (7 vs 4.2)** — combined **+10**. These are exactly the dimensions that matter for (a) the flagship Blog Writing Agent's multi-stage pipeline with a quality-review/escalation loop, (b) longevity across ~40 agents, and (c) the deferred multi-agent topology (ADR-0002). Native checkpointer-based state is a structural fit for multi-step flows; app-owned history threading does not scale as gracefully into branching/looping graphs.

### 6a. Runner-up — Pydantic AI (88), and when to flip

Pydantic AI is a **strong, close runner-up** and genuinely better on **minimalism and ergonomics**: lighter dependencies (#2), native typed structured output and decorator tools with auto-schema (#4), and first-class testing primitives (#7) — combined **+6** over LangGraph. It is the better default **if** the broader agent population turns out to be **mostly simple, single-shot, single-agent** tasks with little multi-step state and no multi-agent orchestration. **Flip the recommendation (supersede this ADR) if**, after building several more agents, the fleet skews simple/stateless — Pydantic AI's lower ceremony would then win on aggregate developer velocity.

### 7. Conditions before flipping ADR-0001 to Accepted

1. **Live smoke test (required):** run the reference agent on **real Vertex (GCP-first)** through LiteLLM for the winner — and ideally the runner-up — to confirm end-to-end provider-agnostic routing with real tokens and real cost metrics. Offline runs cannot prove the live LiteLLM path.
2. **Independent Codex pass (required):** have Codex cross-verify both tracks against Section 4 (leakage, abstraction, swap validity, glue, eval/observability). Section 4 above is a self-review, not that pass.
3. Only after (1) and (2): apply the Section 9 text and set status to **Accepted**.

---

## 8. Consequences / trade-offs (for the ADR)

**Accepted because:** best fit for stateful, multi-step, and (future) multi-agent flows; most mature/widely-deployed; native durable state; cleanly satisfies the platform's hard constraints (no cloud SDK in `agent/`, model access only via `LLMProvider`→LiteLLM, cloud-by-config).

**Trade-offs we accept:**
- **More boilerplate per agent** (explicit graph nodes/edges) than Pydantic AI's terser loop. *Mitigation:* the scaffold generates the graph/node/edge skeleton so no agent hand-writes it.
- **We forgo Pydantic AI's native typed-output ergonomics.** *Mitigation:* keep Pydantic schemas as the I/O contract and validate in a node (a small shared helper can wrap "LLM text → validated model").
- **Heavier dependency tree** (langchain-core et al.). *Mitigation:* pin versions; the `no_cloud_sdk` guard prevents vendor imports regardless.
- **Framework upgrade risk** (both ecosystems move fast). *Mitigation:* pin both frameworks; re-run the bake-off eval on upgrade.

**Reinforced platform rules (unchanged by this choice):** model access only through `LLMProvider`; state via the framework checkpointer; observability via the shared `Telemetry` (OpenTelemetry in production); the `no_cloud_sdk` CI guard stays on and — per ADR-0003 — also catches STT SDK imports.

**Revisit trigger:** supersede if the agent fleet proves predominantly simple/stateless/single-agent (then reconsider Pydantic AI).

---

## 9. Paste-ready text to update ADR-0001 (Proposed → Accepted)

> Apply **after** the live smoke test and the independent Codex pass (Section 7). The architect ratifies.

```markdown
## Status
Accepted — <DATE>. Ratified by <architect> after the offline bake-off (repo: bakeoff/),
a live Vertex/LiteLLM smoke test, and independent Codex cross-verification.

## Decision
Adopt **LangGraph + LiteLLM + Pydantic** as the platform agent framework for the scaffold
and all agents.

Rationale: in the reference-agent bake-off (lookup-and-summarize), both LangGraph and
Pydantic AI scored full marks on provider/model agnosticism (criterion #1 = 5/5) and both
passed the identical eval, the no-cloud-SDK import check, the config-only provider/model
swap (Vertex -> Anthropic with zero agent-code change), and the trace/log/token-cost checks.
With #1 tied, the ADR-0001 tie-break defers to platform-longevity dimensions, where LangGraph
leads: state/memory (native MemorySaver checkpointer), maturity/ecosystem, and multi-agent
readiness. Weighted totals: LangGraph 92/100, Pydantic AI 88/100.

Pydantic AI is recorded as a strong runner-up (lighter dependencies, native typed outputs,
first-class testing primitives) and is the preferred choice should the agent fleet prove
predominantly simple, single-shot, and single-agent.

## Consequences
- Model access only via the core LLMProvider (LiteLLM under the hood); no cloud SDK in
  agent/ — enforced by the no_cloud_sdk CI guard (extended per ADR-0003 to STT SDKs).
- State via the LangGraph checkpointer; observability via the shared Telemetry (OTel in prod).
- The scaffold generates the LangGraph node/edge skeleton so agents don't hand-write it.
- Pydantic schemas remain the I/O contract; validate LLM output in a node.
- Pin LangGraph + langchain-core; re-run the bake-off eval on upgrade.

## Runner-up and why not
Pydantic AI (88/100). Lower ceremony and native typed output, but app-owned state threading
and a younger ecosystem make it a weaker fit for the multi-step flagship pipeline and the
deferred multi-agent topology. Revisit if the fleet proves mostly simple/stateless.

## Conditions / exceptions
A second framework (e.g., Pydantic AI) may be approved for a specific agent class only if that
class is demonstrably simple/single-shot and the reuse cost of LangGraph is not justified.
```

---

## 10. Suggested next steps (for the architect)

1. **Run the live smoke test** (Vertex via LiteLLM) and the **independent Codex pass** on `bakeoff/` — the two gating conditions in Section 7.
2. If both hold, **apply Section 9** to `docs/adr/ADR-0001-framework-selection.md` and set **Status: Accepted**.
3. Only then proceed to **Phase 2 — Blog Writing Agent `DESIGN.md`** (this bake-off does not start it).
4. Carry forward into the scaffold: the `LLMProvider`→LiteLLM seam, the LangGraph node/edge skeleton as generated boilerplate, the shared `Telemetry`, and the `no_cloud_sdk` CI guard (incl. ADR-0003 STT coverage).

*The bake-off code (shared substrate + both tracks) is included alongside this document for the Codex pass and the live smoke test.*
