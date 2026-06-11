# Agent 01 — Blog Writing Agent (Golden / Reference Agent)

> **Status: Phase 1 complete — approved by the architect (gate passed). Framework resolved via ADR-0001.**
> Planning decisions finalized by the architect; captured here in the playbook §8.1 format.
> **Framework decision completed via the ADR-0001 bake-off. Selected framework for Agent 01 design and implementation: LangGraph + LiteLLM + Pydantic** (close runner-up: Pydantic AI + LiteLLM). The live Vertex/LiteLLM smoke test and the independent Codex review remain pending before final merge. Currency: ₹ (INR); "lakh" = 100,000.

---

## 1. Use case (what we're trying to do)

A high-volume blogger (~5 posts/day) collects rough inspiration as messy **text** (pasted notes, written thoughts, copied internet/reference snippets), **voice** recordings, and **video** clips (reels, podcasts, lectures, interviews, product demos, screen recordings). Today they manually turn that raw material into finished posts, which is slow. **Trigger:** the user submits one or more rough inputs in any supported form. **User:** the blogger / content writer. **Job-to-be-done:** convert messy multi-modal input into a structured, brand-aware, **review-ready blog package** — fast and cheap enough to be worth doing at daily volume, grounded in the user's own ideas (never copied from reference material). **Success:** a draft needing only a light human edit pass, with source/inspiration notes and a quality score. **v1 produces drafts only — it does not publish.**

**Golden-agent mandate.** Agent 01 is the reference pattern the other ~39 agents copy. It must prove, as reusable platform machinery: (1) framework choice, (2) provider abstraction, (3) model routing, (4) typed I/O schemas, (5) cost tracking, (6) evals, (7) observability, (8) access control, (9) prompt-injection safety, (10) a reusable scaffold. Reusable core stays in `packages/core`; only blog-specific stage logic lives in the agent.

**Scope (v1):** three input types — text, voice (transcribed), and video (audio extracted → transcribed; **no** visual/key-frame analysis).

**Out of scope (v1):** publishing to any CMS / website / LinkedIn / social platform; autonomous web search; live scraping; visual video understanding; key-frame analysis; any external write or irreversible action. Pasted reference content is allowed but treated only as untrusted inspiration, never as instructions.

---

## 2. ROI

Computed with the playbook formula `ROI = (Annual value − Annual run cost) ÷ (Build cost + Annual run cost)`.

- **Assumptions:** manual ≈ 60 min/blog; with agent ≈ 20 min/blog incl. human review ⇒ **40 min saved/blog**. 5 blogs/day × 22 days = **110 blogs/month**. Loaded content cost **₹500/hr**.
- **Time saved:** 110 × 40 min = 4,400 min/month ≈ **73 hrs/month**.
- **Annual value:** ≈ ₹36,500/month ⇒ **≈ ₹4.4 lakh/yr** (~₹4,38,000).
- **Annual run cost:** AI + infra ≈ ₹5,000–6,000/month ⇒ **≈ ₹70,000/yr**.
- **Build cost (one-time, this agent):** **≈ ₹1.5 lakh** (higher than a normal agent because it also hardens the template/scaffold/abstractions the other 39 reuse).
- **Net annual value:** ≈ ₹4.4 lakh − ₹0.7 lakh = **≈ ₹3.7 lakh**.
- **Payback:** build ÷ monthly net value (~₹31,000) ≈ **5 months**.
- **Year-1 ROI:** (₹4.38 lakh − ₹0.70 lakh) ÷ (₹1.50 lakh + ₹0.70 lakh) ≈ **167%** (~160–170%).

---

## 3. Efficiency

- **Baseline (today):** ~60 min/blog, fully manual.
- **Target (with agent):** ~20 min/blog including human review/editing; ≤ blended **₹25/blog** (hard ceiling ₹50).
- **Actual (post-launch):** measure time/cost/quality after launch and feed back. An agent with no measurable efficiency gain shouldn't be built.

---

## 4. Architecture sketch _(formalized in DESIGN.md)_

**Pipeline (cloud-agnostic "brain"):**
`Input → [if voice/video] transcription → Input normalization → Idea extraction → Blog planning → Draft generation → Quality review (→ escalate if low) → Final structured output`

**Video path (v1):** `Video upload → audio extraction (ffmpeg) → transcription → (same pipeline as above)`. No key-frame/visual analysis in v1.

- **Orchestration framework:** **Decided via the ADR-0001 bake-off — LangGraph + LiteLLM + Pydantic** (LangGraph 92 vs Pydantic AI 88), chosen because the agent is a multi-stage pipeline with a conditional quality-escalation loop and shared stage state, and LangGraph is the stronger fit for stateful / multi-step (and future multi-agent) flows. **Pydantic AI + LiteLLM** was the close runner-up; **Google ADK** remained reference-only (GCP-coupling risk). Live Vertex/LiteLLM smoke test + independent Codex review pending before final merge.
- **Stage I/O:** every stage has a typed Pydantic input/output schema (the reusable "typed I/O" pattern).
- **Model strategy (cost-tiered, via `LLMProvider` + LiteLLM, model chosen per stage by config):**
  - *Cheap tier* — input cleaning, idea extraction, classification, outline/planning.
  - *Strong tier* — main draft generation and quality review.
  - *Escalation* — if quality < threshold, re-draft on the strong tier, under a **hard retry/cost cap**; must respect the ₹50/blog ceiling. If still sub-threshold within caps, return the best draft flagged below-threshold with improvement suggestions.
  - *Caching* — repeated user style preferences, repeated reference processing, repeated instructions.
- **Transcription:** through the new **`TranscriptionProvider`** abstraction (accepted decision — see §7). Provider-routable and config-selected, like `LLMProvider` / `SecretStore` / `ObjectStorage`; never a direct SDK call in `agent/`.
- **Audio extraction:** a shared deterministic preprocessing utility (ffmpeg or equivalent), portable and cloud-free — **not** a provider. **No `VisionProvider` in v1.**
- **Storage:** uploads (audio/video) and drafts via the `ObjectStorage` abstraction; raw media on short/no retention (see §5).
- **Cloud-agnostic by construction:** `agent/` imports **only** abstraction interfaces — no `google.cloud` / `boto3` / `azure.*`; cloud selected by config; **GCP wired first, Bedrock + Azure stubbed** behind the same interfaces. Built as a self-contained unit with a clean I/O boundary (ADR-0001 interim topology rule).
- **Runtime quality reviewer vs CI eval gate:** the in-pipeline reviewer is a *component*; the CI eval threshold is the *gate the agent must clear to ship*. Distinct things.

---

## 5. Access control

### 5.1 Identity, reads, writes, restrictions
- **Invokers:** the blogger / content writer. _[Exact trigger surface confirmed at design.]_
- **Runs as (identity):** its own least-privilege GCP service account — no shared/"god" credentials.
- **Reads:** user-provided text input; voice transcripts; video transcripts; user writing preferences; optional past approved blog samples. Read-only, scoped.
- **Writes:** generated blog drafts; quality scores; logs; cost metrics; evaluation metrics.
- **Cannot (v1):** publish externally; send to social media; modify external CMS data; take any irreversible external action.
- **Future external actions** (publishing, external writes) require explicit **human approval (HITL)** and added scopes/OAuth — out of scope for v1.
- **Secrets:** model API keys, transcription API keys, storage credentials, database credentials — all via the **`SecretStore`** abstraction; never in code or images.
- **Audit:** every tool invocation and any external action logged with who/what/when.

### 5.2 Data classification & retention
- **Sensitivity:** treat all input as **sensitive user content** — text/voice/video may contain private thoughts, business ideas, names, client details, or PII.
- **Raw audio/video:** do not store, or store with **short retention** only; delete after transcription where possible.
- **Transcripts / draft history / writing preferences:** store only if needed, with a defined retention policy (set in DESIGN).
- **Residency:** resolved — data residency is a **deployment/config concern**; the agent logic bakes in no region or cloud, and the same image runs wherever config selects. Data-residency constraints may still restrict which cloud/region a given deployment chooses.

### 5.3 Guardrails
- **Untrusted-content rule:** all pasted text, reference content, **transcripts, and video-derived text** are treated as *data*, never instructions. A spoken or pasted "ignore previous instructions" is ignored.
- **Trust boundary:** the input normalizer separates the user's own ideas from copied/reference material and passes reference material as clearly-delimited, non-instruction context.
- **Originality / IP:** the agent produces **original** drafts from the user's idea — it must not copy or spin reference content. Originality is enforced in the quality reviewer (similarity check against the supplied reference material).
- **Injection defense:** input/output filtering, tool allow-lists, untrusted-by-default tool/data output (platform baseline §3.4).

---

## 6. Requirements

### 6.1 Functional
- Accept text, voice, and video input (video = audio path only in v1).
- Transcribe voice and extracted-video audio to text via `TranscriptionProvider`.
- Normalize messy input; extract topic, audience, tone, intent, key points; separate user ideas from reference material.
- Plan the post (title options, outline, angle, SEO keywords, structure).
- Generate the draft; run the quality review; escalate within caps if below threshold.
- Return the **review-ready blog package:** blog title; alternative title options; short summary; full blog draft; suggested SEO keywords; suggested tags; meta description; source/inspiration notes; quality score; improvement suggestions if quality is below threshold.

### 6.2 Non-functional
- **Latency (batch-tolerant; design targets from DESIGN.md, not hard SLAs in v1):** text-to-draft **p50 ~20s / p95 ~45s**; voice-to-draft **p50 ~45s / p95 ~90s**; video-to-draft **p50 ~60s / p95 ~120s** (voice/video include transcription; an escalation adds one draft+review cycle).
- **Availability:** best-effort, **batch-style v1** — single blogger, ~5 blogs/day; **no HA requirement for v1**. Graceful failure with a structured terminal status is preferred over strict uptime guarantees.
- **Compliance / residency:** data residency is a **deployment/config concern** — the agent logic must **not** bake in a region or cloud; the same agent image runs in whichever cloud/region the config selects.

### 6.3 Cost (hard requirements)
- **Per-blog cost targets:** text-to-blog **< ₹10–15**; voice-to-blog **< ₹20–30**; video-to-blog **< ₹30–50**; blended average **< ₹25**.
- **Hard ceiling: ₹50/blog** — the tiered-model strategy and the capped escalation loop must keep every request under this.

### 6.4 Quality & evaluation
- **Quality score: out of 100**, by this rubric:

| Criterion | Points |
|---|---:|
| Structure and flow | 15 |
| Clarity and readability | 15 |
| Idea coverage | 15 |
| Originality | 15 |
| Tone and audience fit | 10 |
| SEO usefulness | 10 |
| Factual safety and source handling | 10 |
| Grammar and polish | 5 |
| Engagement value | 5 |
| **Total** | **100** |

- **Passing threshold:** ≥ **80/100**. **Strong output:** ≥ **90/100**.
- **Hard-fail conditions (automatic fail regardless of numeric score):** the blog copies or closely spins pasted internet/reference content; the agent follows prompt-injection instructions from pasted text/transcript/reference; the blog ignores the user's main idea; very poor structure; unsafe or unsupported factual claims; not review-ready.
- **Pass rule:** a draft passes only if score ≥ 80 **and** no hard-fail condition triggers.
- **Eval-gated:** the eval suite scores **end-to-end** (not per stage) and is wired as a CI gate; thresholds versioned to prevent eval rot.

### 6.5 Observability
- Emit traces, structured JSON logs, and **per-stage token/cost metrics** (feeds the cost dashboard and the ₹/blog ceiling check), plus the quality/eval metrics above — all cloud-neutral (OpenTelemetry).

---

## 7. Resolved decisions & DESIGN.md coverage

- **Framework (ADR-0001): resolved.** The bake-off built the trivial reference agent in both LangGraph and Pydantic AI and scored them against the weighted criteria; **LangGraph + LiteLLM + Pydantic** was selected (92 vs 88) and the decision + rationale recorded in ADR-0001. Live Vertex/LiteLLM smoke test + independent Codex review remain pending before final merge.
- **`TranscriptionProvider` (accepted):** add to `packages/core` as a reusable provider abstraction; record as **ADR-0003** (extend core abstraction set + policy for adding modality providers). No `VisionProvider` in v1.
- **Retrieval in v1: resolved — direct-context only.** Ground on writing preferences and (optional) past approved samples using **direct context only — no vector store and no `EmbeddingProvider` in v1**. (Semantic retrieval stays a future enhancement; if ever justified it is added behind abstractions, e.g. pgvector — see DESIGN.md §16.)
- **DESIGN.md (complete) covers:** the stage-by-stage orchestration graph (incl. the escalation loop + retry/cost caps); a tools table (inputs/outputs/side-effects/permissions); the model-tier/routing map (tier per stage, escalation rule, caching points); the trust-boundary design for reference content + transcripts; the transcription + audio-extraction subsystem; storage/retention design for raw media; prompt strategy + output schema per stage; the provider-neutral check; the eval plan (datasets, metrics, end-to-end thresholds wired to CI); and sprint placement + dependencies.
- **SLOs (set in DESIGN, imported to §6.2):** latency p50/p95 targets, best-effort batch availability (no HA in v1), and residency-by-config.

---

### Phase 1 gate checklist (architect)
- [x] Use case + v1 scope/out-of-scope correct
- [x] ROI, cost ceilings, and efficiency targets agreed
- [x] Access control least-privilege; v1 = no external writes; secrets via `SecretStore`
- [x] Data classification + retention agreed; guardrails (untrusted content + originality) agreed
- [x] Functional + non-functional requirements agreed; quality rubric + hard-fail rule + ≥80 threshold agreed
- [x] Open decisions routed/closed (framework → ADR-0001 **decided: LangGraph + LiteLLM + Pydantic**; `TranscriptionProvider` → ADR-0003 **accepted**; retrieval → **resolved in DESIGN: direct-context for v1, no vector store**)

**Gate status: PASSED — architect sign-off recorded.** Framework resolved (ADR-0001); Phase 2 `DESIGN.md` complete. Remaining before final merge: live Vertex/LiteLLM smoke test + independent Codex review.

_Once the scaffold CLI exists, this file belongs at `agents/agent-01-blog-writer/AGENT_SPEC.md`._
