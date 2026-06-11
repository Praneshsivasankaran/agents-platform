# ADR-0003: Add `TranscriptionProvider` to Core Abstractions

**Date:** 2026-06-04
**Status:** Accepted
**Owner:** _[Human architect]_
**Scope:** Program-level / `packages/core` — applies to every agent that ingests audio or video.
**Independent of:** ADR-0001 (framework selection). This decision concerns the **provider abstraction layer**, which sits *beneath* whatever orchestration framework wins. It holds equally for LangGraph + LiteLLM + Pydantic, Pydantic AI + LiteLLM, or any other framework.

> Captures the decision — accepted during Agent 01 planning — to make speech-to-text a reusable core provider abstraction rather than blog-agent-specific code, plus the related sub-decisions on video audio extraction and vision.

---

## Context

Agent 01 (Blog Writing Agent, the golden/reference agent) ingests **voice** and **video** input. Both require **speech-to-text (STT)**: voice is transcribed directly; in v1, video has its audio extracted and then transcribed (no visual analysis). STT is the first non-LLM external-inference capability the platform needs, so where and how it lives sets a precedent for the other ~39 agents.

Constraints from the playbook and ADR-0001:

- **Cloud-agnostic is the #1 non-negotiable.** Agent logic must not import a cloud/provider SDK; cloud is selected by config; GCP is wired first, Bedrock + Azure stubbed behind the same interfaces (playbook §2.1, §3.2; ADR-0001).
- **`agent/` imports only abstraction interfaces.** STT backends (Google STT / Vertex, AWS Transcribe, Azure Speech, or neutral engines such as Whisper / Deepgram) are cloud/vendor-specific and would otherwise leak into agent code — agnostic drift is the program's top risk (§9).
- **One template, reused 40×.** The golden agent is the pattern others copy, so blog-specific plumbing inside it propagates to all 39. Several other planned agents touch audio (meeting notes, call transcripts), so STT is cross-cutting, not blog-specific.
- **Secrets via `SecretStore`.** Transcription API keys are explicitly in scope and must not sit in code or images (Agent 01 spec §5.1).

The open question: **where does STT live, and in what shape?** And, relatedly: is video audio extraction also a "provider," and do we need a vision abstraction now?

---

## Options considered

**A. STT inline in the blog agent** (a direct backend call or local helper inside `agent/`).
*Against:* couples agent logic to a specific cloud/vendor SDK → agnostic drift; not reusable by other audio agents without copy-paste (violates "generate from scaffold, never hand-roll"); bloats the golden template with blog-specific I/O. **Rejected.**

**B. STT as a dedicated `TranscriptionProvider` abstraction in `packages/core`** (a peer of `LLMProvider`, `SecretStore`, `ObjectStorage`).
*For:* same isolation pattern the platform already uses; provider-routable and config-selected; reusable by every audio/video agent; keeps `agent/` SDK-free; credentials flow through `SecretStore`. *Against:* one more interface to maintain across clouds, plus thin per-provider glue. **Chosen.**

**C. Route STT through the existing `LLMProvider` / LiteLLM layer** (treat transcription as "just another model call").
*Against:* transcription has a distinct I/O shape (audio in; transcript out; options like language, timestamps, diarization) and distinct providers/pricing from chat models; folding it into `LLMProvider` muddies an otherwise clean interface and complicates per-capability cost tracking. A narrow peer abstraction is cleaner. (An *implementation* of `TranscriptionProvider` may internally use an audio-capable router — that detail stays hidden behind the interface.) **Rejected as the agent-facing shape.**

> A broad single `MediaProvider` covering extraction + STT + vision was also rejected: it conflates deterministic local processing with cloud inference and is harder to test and reason about than narrow, single-purpose abstractions.

---

## Decision

### 1. STT becomes a first-class core abstraction: `TranscriptionProvider` in `packages/core`
A peer of `LLMProvider`, `EmbeddingProvider`, `SecretStore`, `ObjectStorage`, and `Telemetry`. Agents that need transcription depend only on this interface; they never import an STT SDK.

Why it belongs in core, not the agent:
- **Cross-cutting.** Multiple planned agents ingest audio/video; the capability must be shared, not re-implemented per agent.
- **Cloud/vendor-variable.** It is exactly the kind of capability the abstraction layer exists to isolate; leaving it in agent code is the agnostic-drift failure mode the program is built to avoid.
- **Keeps the golden template clean.** The blog agent uses transcription as a configured capability, so a future text-only agent copies the same skeleton and simply doesn't enable it.

### 2. It stays provider-routable and config-selected
- The **interface is stable**; implementations vary by backend — `transcribe(audio_ref, options) -> Transcript`-style typed I/O (Pydantic), with options such as language and (optionally) timestamps/diarization, returning a typed result.
- **Implementations:** GCP wired first; AWS and Azure (and, if desired, a provider-neutral engine such as Whisper) **stubbed behind the same interface with interface-level tests** — mirroring the playbook's "wire GCP now, stub the rest" rule.
- **Selection by config, not code:** a key like `transcription.provider = gcp | aws | azure | whisper` picks the implementation at startup, exactly as `CLOUD = gcp | bedrock | azure` selects cloud implementations. Swapping backends is a config change plus filling in a stub — never an agent rewrite.
- **Credentials** (transcription API keys) come from `SecretStore`; none in code or images.

### 3. Video audio extraction is a shared deterministic utility, not a provider
- Extraction (demuxing audio from a video container, e.g., via ffmpeg) is **deterministic, local, compute-only** — no model, no external inference, **no cloud variance**. It runs identically in any container on any cloud.
- A provider abstraction exists to hide *which cloud/vendor* fulfills a variable capability. Extraction has nothing to route and no variance to hide, so wrapping it in a provider would be ceremony with no payoff.
- It therefore lives as a **shared preprocessing utility in core** (e.g., `core/media/extract_audio`), portable and cloud-free, producing an audio artifact that is then handed to `TranscriptionProvider`.
- _(If a managed cloud media service is ever needed — say, for very large files — that reintroduces cloud variance and could be wrapped behind an abstraction at that point. Out of scope for v1.)_

### 4. `VisionProvider` is deferred for v1 — but the path stays additive
- Agent 01 v1 explicitly excludes visual/key-frame analysis, so there is **no v1 consumer** of a vision capability. Adding `VisionProvider` now would be speculative abstraction (YAGNI): an interface with no exercised implementation, no eval, and ongoing maintenance cost.
- Deferral **must not foreclose.** The abstraction set is designed so a future `VisionProvider` slots in **purely additively** — a new core interface + config key + GCP-first/stubbed implementations — using the same pattern as `TranscriptionProvider`. When key-frame/visual analysis enters scope (a later blog-agent version or another agent), it triggers its own ADR and drops in without redesign.

### 5. Modality-provider policy (established here, reused going forward)
- A capability becomes a **narrow core provider abstraction** when it is needed by ≥ 1 agent **and** is fulfilled by a cloud/vendor-variable external service (e.g., STT today; future vision/OCR; embeddings). Such providers are provider-routable, config-selected, GCP-wired-first with the rest stubbed + interface-tested, with secrets via `SecretStore`, and covered by the agnostic-drift CI guard.
- A capability stays a **shared deterministic utility** when it is local, deterministic, and free of cloud variance (e.g., audio extraction, file parsing).
- **Don't pre-add providers without a real consumer** (YAGNI); add them when a use case demands one. This keeps the abstraction set lean and honest while preserving agnosticism.

---

## Consequences

**Locks in / requires:**
- `packages/core` gains a `TranscriptionProvider` interface and a GCP implementation; AWS + Azure (and optionally Whisper) implementations are stubbed with interface-level tests.
- A `transcription.provider` config key (per cloud/provider), selected at startup; transcription credentials sourced from `SecretStore`.
- The **agnostic-drift CI guard** (the "no cloud SDK in `agent/`" lint/architecture test, §9) is **extended to flag STT SDK imports** (e.g., `google.cloud.speech`, AWS Transcribe clients, `azure.cognitiveservices.speech`) inside `agent/`.
- The **scaffold / CLI**-generated skeleton exposes **optional transcription wiring, off by default** — multimodal agents enable it by config; text-only agents inherit the skeleton without carrying it (supports the reusable-base goal).
- A **shared media utility** (`core/media/…`) using ffmpeg-or-equivalent; the **Dockerfile must install ffmpeg**. Pick an appropriately licensed build (e.g., an LGPL build) and treat the media tool's license as a watch-item.
- **Observability/cost:** transcription is a per-request cost + latency contributor; the per-stage cost metrics already required by the Agent 01 spec must include the transcription stage (feeds the ₹/blog ceiling check). Transcription-quality measurement (e.g., WER on a small set) is a possible DESIGN-time addition, not required here.

**Accepted trade-offs:**
- One additional cross-cloud interface to maintain, plus thin per-provider glue.
- ffmpeg as a container dependency (image size + licensing diligence).

**Follow-on ADRs triggered:**
- A future **`VisionProvider` ADR** if/when key-frame or visual analysis enters scope (governed by the modality-provider policy above).
- No change to ADR-0001 — this decision is orthogonal to the framework choice.

---

## Related

- Aligns with playbook §3.2 (provider abstraction layer), §3.3 (scaffold reuse), §3.4 (secrets via `SecretStore`), §9 (agnostic-drift risk), and ADR-0001 (agnosticism as the #1 non-negotiable; ADK reference-only).
- Consumed first by Agent 01 (Blog Writing Agent) for voice + video → transcript; reusable by any future audio/video agent.
- Independent of ADR-0001's pending framework decision — `TranscriptionProvider` sits beneath the orchestration framework and holds regardless of which wins.
- Once the monorepo exists, this belongs at `docs/adr/ADR-0003-transcription-provider.md`.
