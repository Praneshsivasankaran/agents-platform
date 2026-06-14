# Agent 02 - Content Repurposing Agent Design

## Reference Pattern

Agent 02 follows Agent 01's reusable platform pattern:

- LangGraph for workflow topology, state, branching, revision, and escalation
- LiteLLM through shared `LLMProvider`
- `CoreContractModel` schemas for typed immutable contracts
- central `core.cost` authorization and usage ledger
- telemetry through `Telemetry`
- provider-neutral storage through `ObjectStorage`
- no cloud SDKs inside `agent/`

## Workflow

Canonical workflow:

```text
intake
-> validate_source
-> parse_source
-> extract_core_message
-> extract_audience_value
-> generate_content_angles
-> select_platform_strategy
-> load_platform_rules
-> generate_platform_drafts
-> validate_platform_fit
-> check_factual_consistency
-> usefulness_review
-> review_quality
-> revise_weak_outputs
-> finalize
```

`review_quality` either finalizes, routes terminal hard-fails to human review,
or sends retriable quality issues to `revise_weak_outputs`. The revision loop is
bounded by config and by the Rs.30/package cost gate.

## State

`Agent02State` contains the serialized request, parsed source, core message,
audience value, content angles, platform strategies/rules/drafts, validation
reports, factual/usefulness/quality reports, revision count, terminal status,
sanitized errors, and the cost ledger.

`cost_usage` and `hard_fails` are LangGraph reducers using `operator.add`.

## Schemas

All provider-facing and terminal contracts live in `agent/schemas.py` and
subclass `CoreContractModel`.

Important schemas:

- `SourceContent`
- `Agent02Request`
- `SourceClaim`
- `ParsedSource`
- `CoreMessage`
- `AudienceValue`
- `ContentAngle`
- `PlatformStrategy`
- `PlatformRules`
- `PlatformDraft`
- `PlatformValidationResult`
- `FactualConsistencyReport`
- `UsefulnessReport`
- `QualityReport`
- `StageCost`
- `CostUsage`
- `RepurposedContentPackage`

Schemas use immutable tuples and strict validation to match the shared provider
structured-output contract.

## Prompt Strategy

Prompt helpers keep trust boundaries explicit:

- trusted system instructions
- user campaign context
- untrusted source content
- agent-generated intermediate data

Closing delimiter text inside source or agent data is escaped so source content
cannot break out of its prompt zone.

## Validators

Deterministic validators implement the v1 quality and safety gate:

- source thickness and Agent 01 status validation
- source claim extraction
- platform rules for LinkedIn, Instagram, X/Twitter, short-video script, and
  optional newsletter/email
- platform fit checks
- mechanical factual consistency checks
- generic-content and duplicate-content detection
- weak CTA detection and revision
- confidential/internal marker detection

External platform APIs are not used.

## Hard-Fail Rules

Terminal hard-fails:

- prompt injection followed into drafts
- fake facts or fake statistics
- unsupported terminal claims
- changed source meaning
- fake publishing/posting/scheduling claims
- attempted external action
- confidential/internal content exposed
- cost ceiling exceeded
- direct cloud SDK import

Retriable quality failures:

- generic content
- weak hook
- weak CTA
- platform mismatch
- too repetitive
- low usefulness
- same content reused
- poor formatting
- weak audience relevance
- weak claim grounding

Retriable failures may enter the revision loop. Terminal hard-fails finalize as
`needs_human`.

## Cost

Billable stages:

- `generate_platform_drafts`
- `check_factual_consistency`
- `review_quality`
- `revise_weak_outputs`

Each billable stage estimates prompt tokens, calls `authorize_call`, passes
`_authorized_prompt_tokens`, records usage, and appends a `StageCost`. The graph
guard also checks post-node totals against the Rs.30 ceiling.

## Observability

The config registers Agent 02 node spans, route decisions, storage events, and
quality/cost metrics. Telemetry receives structured low-cardinality attributes
only. Raw source text and generated drafts are not logged.

## Config

`config/base.yaml` is the offline mock config and has the Rs.30/package ceiling.
`config/gcp.yaml`, `config/bedrock.yaml`, and `config/azure.yaml` preserve the
same provider-selected shape. GCP is the first real target; AWS and Azure remain
interface-complete stubs behind the same abstractions.

## Eval Plan

The offline eval suite covers:

- clean blog
- long technical blog
- weak CTA
- generic/boring source
- multi-platform request with newsletter
- source prompt injection
- confidential/internal source
- thin input

Eval pass criteria emphasize content quality: quality >= 85, factual
consistency >= 90, platform fit >= 85, usefulness >= 85, CTA clarity >= 85, no
hard-fails for pass cases, adversarial terminal detection, and cost <= Rs.30.
