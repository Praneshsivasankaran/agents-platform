# packages/core

Structured-output constraints use one shared normalization path for pre-call validation and mock
generation. Contradictory, annotation-incompatible, non-finite, and unsupported non-deterministic
constraints fail closed before provider calls; valid constrained unions generate deterministically.

Shared, **cloud-neutral** provider abstractions + utilities used by every agent. Agent
logic imports its seams from here and nothing cloud-specific.

## Increment 6 (GCP/Vertex plus transcription/media path under review)
- `interfaces/` — `LLMProvider`, `TranscriptionProvider`, `ObjectStorage`, `SecretStore`, `Telemetry` ABCs + Pydantic contracts (`Usage`, `LLMResponse`, `ToolCall`, `Transcript`, `TimestampSegment`). `interfaces/errors.py` defines `BillableProviderError` + `BILLABLE_FAILURE_CATEGORIES`: a cost-accountable provider failure carrying ONLY an allowlisted, content-free failure category string and the incurred/estimated `Usage` — never an exception object, class name, or raw message. `interfaces/base.py` exports `validate_structured_schema(schema)`: a shared pre-call validator that recursively inspects every Pydantic field annotation in a `CoreContractModel` subclass and raises `ValueError` (non-billable, before any provider call) if any field uses a mutable container (`list`/`dict`/`set`), `Any`, a plain `BaseModel` subclass, or an unsupported annotation type (fail-closed); verifies the effective Pydantic config (frozen=True, extra='forbid', allow_inf_nan=False, validate_default=True — exact comparisons); rejects schemas with private attributes, `@computed_field`, custom `@model_serializer`/`@field_serializer`, or a `model_post_init` override; validates `Literal` members (only scalar str/bytes/bool/int/finite-float/None — Enum members rejected as not deeply immutable); performs a full deep-immutability walk on concrete defaults; rejects all `default_factory` except the exact built-in `tuple`; and runs a recursive-termination analysis (honoring field `min_length`) that rejects any schema with no finite construction path (e.g. `tuple[Self]`, `tuple[Self, ...] = Field(min_length>=1)`, `Self`-only unions, mutual required cycles) while accepting terminating recursion (`tuple[Self, ...]`, `Self | str`, `Optional[Self]`, terminating mutual cycles). Runtime enforcement in `assert_deeply_immutable()` mirrors the config/private/computed/serializer/post-init checks, rejects Enum members, undeclared instance `__dict__` keys, and non-empty `__pydantic_private__`, so `LLMResponse._validate_payload` is belt-and-suspenders for any value bypassing pre-call. `MockLLMProvider` uses the public `annotation_can_terminate` helper to deterministically pick a terminating union branch and guards against construction cycles. Both `LiteLLMProvider` and `MockLLMProvider` call `validate_structured_schema` before doing any cost estimation or provider invocation.
- `providers/mock/` — offline mock impls of every seam (keyless, deterministic, constraint-aware structured output). `StdoutTelemetry` uses a **provenance-based** security model: registered labels (platform set + per-agent injected `extra_labels`), per-agent dimension enums (injected, not hardcoded), wholesale redaction of nested structures (no recursion), numeric-PII default-redaction, and finite-only metric values (see its module docstring).
- `providers/gcp/` - real GCP backends: `LiteLLMProvider`, `GCSObjectStorage`, and
  `GCPTranscriptionProvider`. Real STT uses configured non-zero provider-native pricing,
  bounded normalized WAV input, and billable-failure cost preservation.
- `checks/no_cloud_sdk.py` — AST import guard (cloud + STT + direct-model SDKs incl. `google.genai`/`google.generativeai`/`litellm`; alias-aware dynamic-import detection; fail-closed; auto-discovers all `agents/*/agent/`)
- `factory.py` — config-driven provider selection (mock + GCP Vertex/STT wired; Bedrock/Azure raise `NotImplementedError`)
- `cost/meter.py` (cost ledger + `estimate_prompt_tokens`), `cost/budget.py` (`authorize_call`), `config/loader.py`, `media/extract_audio.py`
- CI: static compile → guard → import smoke → tests (offline, no cloud creds; count in CI output)

Interface modules import only **Pydantic + the standard library** — never a cloud SDK.

**Dependency boundary:** cloud/provider SDKs are permitted **only** in
`providers/{gcp,bedrock,azure}/` (the provider-implementation layer, currently empty placeholder
packages). They are forbidden in `agents/*/agent/`. The no-cloud-SDK import guard scans
`agents/*/agent/` and must **not** scan `providers/*`.

## Next increment
- Agent 01 business logic: `agents/agent-01-blog-writer/agent/` (LangGraph nodes, cost gate, quality loop, schemas, state).
- GCP/Vertex real impls (`providers/gcp/`) + Bedrock/Azure stubs.

## Contract tests

These contract tests are **implemented and CI-gated** (`tests/test_contracts.py`). They cover
these **models** — `CoreContractModel`, `Usage`, `LLMResponse`, `ToolCall` (`args`),
`Transcript` / `TimestampSegment` — across these **behaviors**:
- **payload exclusivity** — `LLMResponse` rejects zero or multiple payloads.
- **subclass serialization** — `model_dump()` preserves the concrete `response_schema` fields (`SerializeAsAny`).
- **schema rejection** — `LLMResponse.structured_from` raises on schema mismatch; providers route through it.
- **negative-value rejection** — `Usage` rejects negative tokens / audio / cost.
- **mutation rejection** — frozen models reject post-construction mutation.
- **currency fail-closed** — missing/blank currency on a billable `Usage` is rejected; unknown currency fails closed in `core.cost`.
- **transcript metadata** — non-negative `duration_s`/`latency_ms`, `confidence` in `[0,1]`, `start_s <= end_s` segments.
- **validated-copy** — `model_copy(update=...)` / `validated_copy()` revalidate; invalid updates are rejected (cannot bypass invariants).
- **nested-mutation prevention** — `Transcript.segments`/`speakers` are tuples; `ToolCall.args` is a deeply-immutable mapping.
- **transcript timestamp ordering** — segments chronological; segment `end_s` within a known `duration_s`.
- **non-finite rejection** — `inf` / `-inf` / `nan` rejected for all numeric fields (costs, durations, latency, confidence, timestamps).
- **structured deep immutability** — `LLMResponse.structured` must subclass `CoreContractModel` and use immutable nested types.
- **mutable nested structured schema rejection** — a `CoreContractModel` structured schema with a `list`/`dict`/`set` field is rejected.
- **ToolCall args JSON-only validation** — non-JSON values (`set`, Pydantic models, arbitrary objects, non-finite floats) are rejected.
- **ToolCall args deep immutability** — top-level and nested mutation of `args` is impossible.
- **`model_copy(deep=True)` compatibility** — deep copy of contract models (incl. `ToolCall.args`) works.
- **checkpoint/pickle compatibility** — contract models (incl. `ToolCall.args`) pickle and round-trip cleanly.
- **`extra="forbid"`** — unknown/misspelled fields are rejected, not silently ignored.
- **copy/update behavior** — `model_copy(update=...)` and `validated_copy()` revalidate; invalid updates are rejected.
- **structured-output schema enforcement** — `response_schema` must be a `CoreContractModel`; non-conforming or mutable-field schemas are rejected.
- **JSON serialization behavior** — `model_dump(mode="json")` round-trips to plain JSON; `ToolCall.args` serializes to a plain dict.

> Note: Pydantic `frozen=True` is **shallow** — it blocks attribute reassignment but not mutation of
> nested mutable containers. Contract models therefore use immutable nested types (`tuple[...]` +
> the `ToolArgs` JSON value, and `assert_deeply_immutable` for structured payloads) so nested values
> cannot be mutated after construction (see `interfaces/base.py`).

## Promote-from source
The bake-off `common/` core under
`../../Project 2 Agents/Framework BakeOff/bakeoff/bakeoff/common/` is the basis to
**promote + harden** (LLMProvider, Telemetry, SecretStore, the import guard).
