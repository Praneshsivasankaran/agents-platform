# agents-platform

A cloud-agnostic AI agent platform of ~40 reusable agents. The brain (agent logic) is
cloud-neutral; the cloud is selected by **config**, not code. GCP/Vertex is wired first;
AWS Bedrock and Azure will be interface-complete stubs behind the same interfaces (placeholder
directories today; the stubs land in a later increment).

**Agent 01 — Blog Writing Agent** (`agents/agent-01-blog-writer/`) is the golden/reference
agent that hardens the shared scaffold every other agent reuses.

## Status
Structured-output constraint hardening is complete: pre-call validation and offline mocks share
normalized bounds, reject impossible/unsupported constraints, and generate valid constrained unions.
Agent 01 text, voice, and audio-only video paths are implemented and live GCP smoke has passed.
A basic internal FastAPI UI now wraps Agent 01 for local text/voice/video runs.
- Increments 1–3: monorepo skeleton, `packages/core` interfaces, offline mock providers, no-cloud-SDK CI guard, full Agent 01 text-path LangGraph spine (intake → normalize → extract_ideas → plan → cost_gate → draft → review → finalize), cost gate (₹50 ceiling with prompt-token counting), quality loop, and offline mock CI suite.
- Increment 4: agent-agnostic offline eval harness (`packages/evals/`), 7-archetype Agent 01 eval dataset and adapter (`tests/evals/`). CI gates: injection=100%, schema-valid=100%, pass-rate≥80%, per-run cost<₹50, avg cost≤₹25.
- Increment 5 (final repair pass): Corrected Gemini 2.5 Flash pricing ($0.30/$2.50 per 1M). Fully fail-closed usage extraction. Structured output uses the LiteLLM documented form — `response_format` = the Pydantic model itself (LiteLLM handles the Vertex translation); no schema text injected into messages. Merge-queue smoke gate. Strengthened smoke assertions. Constructor validates tiers, location, and fallback pricing coverage. `BillableProviderError` carries only an allowlisted, content-free failure category (never an exception object or class name); raise sites construct-in-except then raise-outside so `__cause__`/`__context__` stay `None` and no provider content can leak. Conservative usage fallback accounts for response-schema overhead and fails closed when estimation is impossible. Structured-output contract fully hardened: `assert_deeply_immutable()` enforces all four config settings with exact comparisons; non-finite floats and private-attribute schemas rejected at runtime; `default_factory` allowlist restricted to exact built-in `tuple`; full deep-immutability walk on concrete defaults; contract-parity parametrized test matrix added. `@computed_field`, `@model_serializer`/`@field_serializer`, and `model_post_init` overrides rejected at both pre-call and runtime; `Literal` members restricted to scalar str/bytes/bool/int/finite-float/None (Enum members rejected — not deeply immutable); recursive schemas validated by proper termination analysis that honors field `min_length` (a schema is rejected iff it has no finite construction path — `tuple[Self]`, `tuple[Self, ...] = Field(min_length>=1)`, and non-terminating unions/mutual cycles rejected, `tuple[Self, ...]`/`Self | str`/`Self | None`/terminating mutual cycles accepted), and the mock deterministically picks a terminating union branch so impossible schemas never reach (or crash) a provider.
- Increment 6: provider-neutral voice/video route, deterministic ffmpeg extraction,
  priced GCP STT, bounded pre-call media validation, transcript-based review,
  billable-failure accounting, and owned-temp cleanup.

See `CLAUDE.md` and `agents/agent-01-blog-writer/DESIGN.md`.

The framework decision is recorded (ADR-0001). The independent Codex implementation review is
**pending**: it does **not** block scaffold setup, but **must pass before final
implementation/merge**, and is **not** claimed complete.

## Provider table

| Provider key       | LLM backend            | Storage backend          | Config file     |
|--------------------|------------------------|--------------------------|-----------------|
| `mock` / `offline` | MockLLMProvider        | InMemoryObjectStorage    | base.yaml       |
| `litellm` / `gcp` / `vertex` / `vertex_ai` | LiteLLMProvider (Vertex AI) | GCSObjectStorage | gcp.yaml |
| `bedrock` / `aws`  | (stub — not yet wired) | (stub — not yet wired)   | bedrock.yaml    |
| `azure`            | (stub — not yet wired) | (stub — not yet wired)   | azure.yaml      |

## Structure
```
packages/core/    shared, cloud-neutral provider interfaces + offline mock providers + CI guard
packages/evals/   shared agent-agnostic offline eval harness (Increment 4)
packages/cli/     `new-agent` scaffold generator (extracted last)
agents/           one folder per agent; agent-01-blog-writer is the golden agent
apps/blog-ui/     basic internal FastAPI/Jinja2 UI for Agent 01
infra/            terraform per cloud (gcp first; aws/azure placeholder) + shared
docs/adr/         architecture decision records (ADR-0001 framework, ADR-0003 transcription, ADR-0004 scaffold-CLI sequencing)
```

## Conventions
- `agents/*/agent/` is cloud-neutral and imports only `core` — enforced by CI.
- Provider/cloud selection flows through config (`base.yaml` = offline mock; `gcp.yaml`; …).
- Evals are CI-gated, not vibe-gated; datasets are versioned to prevent eval rot.

See the platform playbook: [`agent-platform-playbook.md`](agent-platform-playbook.md).
