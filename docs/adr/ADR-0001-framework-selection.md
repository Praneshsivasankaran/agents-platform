# ADR-0001: AI Agent Framework Selection

**Date:** 2026-06-01
**Status:** **Accepted** — framework decision recorded (bake-off complete). Final ratification (live Vertex/LiteLLM smoke test + independent Codex implementation review) pending before implementation/merge.
**Owner:** _[Human architect]_
**Scope:** Sprint 0 / program-level — applies to all 40 agents

> **What this is.** The framework-selection ADR (per playbook §3.1 selection method, §8.4 ADR
> template): candidates, weighted criteria, the identical reference agent built in each, and the
> scoring matrix. **The bake-off has been run and the decision is recorded** (see **Decision** and
> **Consequences** below). The worksheet sections are retained for the record. **Final ratification —
> the live Vertex/LiteLLM smoke test and the independent Codex implementation review — remains
> pending before implementation/merge** (not claimed complete here).

---

## Context

We are building **40 cloud-agnostic AI agents** and will **standardize on one framework** to
maximize reuse (playbook §2.6, §3.1). A second framework is allowed only if a specific agent
class genuinely demands it.

Constraints that drive the choice:

- **Cloud-agnostic is the #1 non-negotiable.** The *same* agent must run on **GCP, AWS Bedrock,
  and Azure** without a rewrite. Cloud is selected by config; agent logic never imports a cloud
  SDK. GCP is wired first; Bedrock + Azure are stubbed behind the same interfaces.
- **A model-routing layer sits *underneath* the framework** (LiteLLM or a thin client) so model
  calls reach Vertex / Bedrock / Azure through one interface (§3.1). The framework must tolerate this.
- **Topology is deliberately deferred** — independent agents vs. multi-agent system (see Related
  Decisions). Therefore the framework **must support both**: usable for standalone agents now, and
  capable of multi-agent orchestration later. "Multi-agent support" stays on the criteria list at
  medium weight rather than being dropped.
- **Per-cloud deploy = containers.** The framework's output must containerize (Docker) and run on
  Cloud Run / ECS Fargate / Container Apps. A framework that forces one cloud's bespoke runtime is
  a strike against agnosticism.

---

## Decision method (per §3.1)

1. Score the candidates below against the weighted criteria (scale **1–5**, 5 = best).
2. Build the **same tiny reference agent** (spec below) in the **top 2** candidates — identical
   behavior, so the comparison is apples-to-apples.
3. Compare the builds on developer experience, how cleanly each tolerates the abstraction layer +
   LiteLLM routing, and the weighted scores.
4. **Record the choice and rationale in the Decision section**, then standardize on the winner.

---

## Candidates

Profiles are honest trade-offs, not endorsements. **Re-verify current capabilities against each
project's docs at decision time** — these evolve quickly.

### A. LangGraph (LangChain) — _playbook safe-default_
- **For:** Mature, large ecosystem; graph-based orchestration; strong multi-agent support; strong
  tracing (LangSmith / OpenTelemetry); broad provider coverage and LiteLLM compatibility.
- **Against:** Heavier; ecosystem churn; more concepts to learn; some abstraction overhead.
- **Agnosticism read:** Strong — provider-neutral via model integrations / LiteLLM; no inherent
  cloud lock-in.

### B. Pydantic AI — _playbook lighter alternative_
- **For:** Lightweight, type-safe, provider-neutral by design; pairs naturally with our Pydantic
  I/O schemas; small surface area, easy to wrap behind our abstractions.
- **Against:** Newer, smaller ecosystem; fewer batteries-included orchestration features (we'd
  supply more glue if we later go multi-agent).
- **Agnosticism read:** Strong — neutral by design.

### C. Google ADK — _included because we're already mining its samples_
- **For:** Clean developer experience; first-class tools / sub-agents / workflows (multi-agent
  ready); good eval harness; a `LiteLlm` model wrapper exists for non-Google providers; the samples
  are an excellent agent-logic reference.
- **Against / agnosticism risk:** Strong **GCP gravity** observed directly in the `adk-samples`
  repo — **164** files import `google.cloud` / `vertexai`, **every** model string observed is a
  Google model (Gemini / Veo / Imagen / Gemma), the deploy pattern is hard-wired to **Vertex AI
  Agent Engine**, and **0** of ~75 samples use the `LiteLlm` multi-provider bridge. Agnosticism is
  *achievable* (LiteLLM routing + quarantining cloud calls behind our abstraction + replacing the
  Vertex deploy with our Docker/Terraform), but it cuts against the framework's grain and partially
  negates its batteries-included appeal.
- **The bake-off must stress-test for C:** does routing models via `LiteLlm` to a non-Google
  provider work with **config-only** changes? Can all `google.cloud` touchpoints sit behind our
  interfaces? Can it run as a plain container **off** Vertex Agent Engine?

> **Proposed top 2 to actually build:** **LangGraph + Pydantic AI** — the playbook's recommended
> pair; both score strongly on the top-weighted agnosticism criterion and span the heavy-vs-light
> axis. **Include ADK as a third** if you want to validate it given our reference work — but its
> agnosticism risk above is the thing to weigh. _Architect to confirm the final 2–3._

---

## Scoring criteria & weights

Weights are a proposed starting point (sum = 100); **adjust to taste**. Score each candidate 1–5;
weighted points earned = `score × weight ÷ 5`.

| # | Criterion | Weight | Why it matters here | LangGraph | Pydantic AI | ADK (opt.) |
|---|---|---:|---|:--:|:--:|:--:|
| 1 | Provider/model agnosticism | 25 | The #1 non-negotiable; GCP→Bedrock→Azure, no rewrites | | | |
| 2 | License & lock-in risk | 10 | Avoid hard coupling to one cloud/vendor | | | |
| 3 | Per-cloud deployment story | 10 | Must containerize; run on Cloud Run / ECS / Container Apps | | | |
| 4 | Tool / function-calling abstraction | 10 | Tools defined once, run on any provider | | | |
| 5 | State & memory model | 10 | State must survive provider swaps | | | |
| 6 | Observability / tracing | 10 | Traces + token/cost metrics across all 40 | | | |
| 7 | Testing & eval support | 10 | Gates depend on eval-in-CI | | | |
| 8 | Maturity & community | 8 | Fewer dead ends over a multi-quarter effort | | | |
| 9 | Multi-agent support | 7 | Kept medium: topology deferred, must stay possible | | | |
| | **Weighted total (/100)** | **100** | | | | |

**Scoring guide for criterion #1 (agnosticism) — judge on evidence, not vibes:**
- **5** — provider chosen purely by config; one routing interface to Vertex/Bedrock/Azure; no cloud
  SDK in agent logic; no cloud-bound deploy.
- **3** — agnostic with moderate glue (e.g., a provider wrapper we maintain); minor cloud-specific edges.
- **1** — provider/cloud baked in; switching means rewrites.

> **Scores recorded — bake-off complete.** Per-criterion scores and rationale live in
> [`BAKEOFF-RESULTS.md`](BAKEOFF-RESULTS.md) (and the plan in `ADR-0001-bakeoff-plan.md`). Headline
> weighted totals: **LangGraph 92 / Pydantic AI 88** (ADK not built — reference-only). Both finalists
> scored 5/5 on criterion #1 (agnosticism); LangGraph led on state/memory, maturity, and multi-agent
> readiness (see **Decision** below).

---

## Reference agent (the identical bake-off probe)

Build this **same** mini-agent in each finalist so the scores are comparable. It deliberately
exercises every criterion:

- **Task:** a trivial "lookup + summarize" agent — takes a short query, calls one tool, returns a
  structured answer.
- **Model call routed via LiteLLM** (or the framework's equivalent) — must be swappable
  Vertex ↔ another provider by **config only**.
- **One tool** (e.g., a stub `get_record(id)` returning canned JSON) — exercises the tool /
  function-calling abstraction and permissioning.
- **Structured I/O** via a Pydantic schema for the response.
- **State across 2 turns** (remembers the prior query) — exercises the state/memory model.
- **One eval** — 1–2 JSON test cases + a threshold, wired to pass/fail in CI.
- **Observability** — emits at least one trace span + a token/cost metric + a structured JSON log.
- **Containerized** — a Dockerfile; runs locally via `docker run`; no cloud-specific runtime required.
- **Agnosticism constraint (the real test):** the agent module imports **only our abstraction
  interfaces** — no `google.cloud.*`, `vertexai.*`, `boto3`, or `azure.*`. Note how much friction
  each framework creates in honoring this.

**Record per finalist:** lines of glue code needed, friction points, whether provider-swap was truly
config-only, eval-in-CI effort, and subjective DX.

---

## Decision

**Decided — bake-off complete.** Chosen framework: **LangGraph + LiteLLM + Pydantic**.

- **Chosen framework:** **LangGraph** (orchestration) + **LiteLLM** (model routing) + **Pydantic** (typed I/O).
- **Why** (weighted scores + reference-agent experience): both finalists tied at the top on criterion #1 (provider/model agnosticism) — each passed the **config-only** provider swap and the **no-cloud-SDK** import check in the identical reference agent. The tie-break went to platform longevity: LangGraph's native checkpointer **state/memory** model, broader **maturity/ecosystem**, and graph-native **multi-agent readiness** (criterion #9) better fit stateful, multi-stage pipelines such as Agent 01's quality-escalation loop. Weighted bake-off total: **LangGraph 92 vs Pydantic AI 88**.
- **Runner-up and why not:** **Pydantic AI + LiteLLM** (close — lighter dependencies, first-class typed outputs/testing). Recorded as the fallback to revisit if the agent fleet proves predominantly simple/stateless. **Google ADK** stayed reference-only (GCP-coupling risk).
- **Conditions / exceptions:** a second framework is permitted only if a future agent class genuinely demands it (playbook §2.6); ADK samples remain a *pattern* reference, never a baseline.
- **Ratification pending merge:** the **live Vertex/LiteLLM smoke test** and the **independent Codex implementation review** must pass before final implementation/merge. This ADR records the decision; it does **not** claim those checks are complete.

---

## Consequences

- **What this locks in:** **LiteLLM** as the model-routing layer beneath the framework (agent logic asks `LLMProvider` for a *tier*, never a vendor model); scaffold wiring on a LangGraph `StateGraph` with typed Pydantic state/I/O and config-selected providers; CI checks — the **no-cloud-SDK import guard** (extended for STT per ADR-0003) and **CI-gated evals**.
- **What becomes harder / accepted trade-off:** LangGraph is heavier with more ecosystem churn than Pydantic AI; mitigated by **locking the framework version** (an exact lockfile is a Debug/Harden task) and keeping agent logic thin so a framework change stays survivable.
- **Follow-on ADRs triggered:** **ADR-0003** (TranscriptionProvider — accepted, orthogonal); **ADR-0004** (scaffold-CLI sequencing — Agent 01 manually scaffolded, `new-agent` CLI extracted afterward). **ADR-0002** (topology) stays deferred; the chosen framework remains multi-agent capable (criterion #9).

---

## Related & pending decisions

### ADR-0002 (proposed): Agent topology — **DEFERRED**
- **Question:** Are the 40 agents *independent* (standalone tools) or a *multi-agent system*
  (agents that call/route to each other)?
- **Status:** Deferred — not enough information yet.
- **Interim rule:** Build every agent as a **self-contained unit with a clean input/output
  boundary**, even if nothing calls it yet (works standalone now, composable later). Do **not** let
  agents share mutable state or import each other directly. A multi-agent system is *additive*
  (independent agents + an orchestration/registry layer + inter-agent contracts), so building
  independent-first forecloses nothing.
- **Trigger to decide:** After the first **5–10 agent specs** exist — the use cases will reveal
  whether anything genuinely wants orchestration (e.g., a router agent, or one agent feeding another).
- **Consequence for this ADR:** the framework must stay **multi-agent capable** (criterion #9).

### Model-routing layer (confirmed)
- **Confirmed:** **LiteLLM** sits underneath the framework; all model calls reach Vertex / Bedrock /
  Azure through one interface. Agent logic asks `LLMProvider` for a *tier*, never a vendor model.

### ADK samples = reference only (decided)
- The `google/adk-samples` repo is adopted as a **reference for agent-logic patterns** (directory
  anatomy; callback hooks for guardrails / audit / HITL; eval-as-pytest-gate; sub-agent / workflow
  shapes) — **not** as a baseline. Its GCP coupling (`google.cloud` / Vertex imports, Agent Engine
  deploy) is **not** imported into our agent code. Holds regardless of which framework wins.

---

_Aligns with playbook §2 (operating principles), §3.1 (framework selection), §3.4 (security
baseline), §8.4 (ADR template), §9 (agnostic-drift risk). Re-verify framework capabilities and
cloud service names against current provider docs before finalizing. Once the monorepo exists, this
belongs at `docs/adr/ADR-0001-framework-selection.md`._
