# Agent 06 - Whitepaper Development Agent DESIGN.md

**Phase:** 2 - Design
**Status:** Design complete for implementation in this increment.
**Framework:** LangGraph + LiteLLM + Pydantic
**Source spec:** `agents/agent-06-whitepaper-development/AGENT_SPEC.md`

Agent 06 turns user-provided business context into a review-ready whitepaper development package. The package is not a final approved publication-ready whitepaper; it is a draft package that requires human review, evidence verification, legal/compliance review where needed, and final approval before publication.

## 1. Scope Guard

Agent 06 v1 is draft-only and context-only.

In scope:

- normalize supplied whitepaper context
- plan a recommended angle
- map supplied and missing evidence
- create a structured whitepaper outline
- draft section-level whitepaper content
- review key claims against evidence status
- detect weak/generic output
- score quality
- assemble a structured package for human review

Out of scope:

- publishing
- CMS writes
- CRM writes
- analytics calls
- email sending
- live web research
- scraping
- external research APIs
- generated charts/images/PDF design
- vector retrieval
- long-term memory
- direct calls to other agents

## 2. Orchestration

The workflow is a single LangGraph `StateGraph` with request-level state and a fixed linear path:

`intake validation -> context normalization -> angle planning -> evidence mapping -> outline generation -> section drafting -> claim/evidence review -> generic-content detection -> quality scoring -> final package assembly`

Every stage returns typed Pydantic contracts or deterministic local results. Billable LLM stages are routed through `LLMProvider`; provider selection and model IDs come from config.

## 3. Nodes

| Node | Tier | Purpose |
|---|---|---|
| `intake_validate` | none | Validate required fields before billable work. Return `needs_more_input` if required inputs are missing or invalid. |
| `normalize_context` | cheap | Convert messy inputs into a compact structured request summary and core positioning facts. |
| `plan_angle` | cheap | Recommend the whitepaper angle, audience promise, and narrative thesis. |
| `map_evidence` | deterministic + optional cheap | Extract key supplied proof points and map each to claim/evidence status. Missing evidence is explicitly recorded. |
| `generate_outline` | cheap | Create a whitepaper outline with required sections and section intent. |
| `draft_sections` | strong | Draft the section content as review-ready whitepaper material, grounded only in supplied context and evidence map. |
| `review_claims` | deterministic | Extract key claims from the draft, assign evidence status, and flag unsupported verified-sounding claims. |
| `detect_generic_content` | deterministic | Flag vague, reusable, placeholder, or generic AI-style wording. Generic output cannot pass. |
| `score_quality` | deterministic | Score against the 100-point rubric and apply hard-fail rules. |
| `assemble_package` | none | Build the terminal `WhitepaperDevelopmentPackage` with status, costs, risks, missing evidence, and suggestions. |

## 4. Cost Strategy

Agent 06 uses a Rs50/request hard ceiling in v1.

- Cheap tier: context normalization, angle planning, outline generation.
- Strong tier: section drafting.
- Deterministic checks: intake validation, evidence coverage, claim review, generic-content detection, scoring, assembly.
- Pre-call authorization estimates the prompt and output caps before every billable provider call.
- If budget is insufficient before a provider call, the workflow uses deterministic fallback where possible and returns `needs_review_budget_limited`; it does not exceed the ceiling.
- Concrete model names live only in `config/*.yaml`.

## 5. Provider Neutrality

Agent code depends only on shared abstractions:

- `LLMProvider` for model calls through LiteLLM
- `ObjectStorage` if persistence is enabled
- `SecretStore` for provider secrets
- `Telemetry` for logs/traces/metrics

Rules:

- no direct cloud SDK imports inside `agents/agent-06-whitepaper-development/agent/`
- provider selected by config only
- GCP/Vertex is the live first target through the existing `core.factory`
- Bedrock and Azure overlays stay structurally compatible stubs
- model names never appear in agent code

Agent 06 has no audio/video input in v1, so it does not use `TranscriptionProvider`. If voice/video input is added later, transcription must use ADR-0003.

## 6. State Model

`Agent06State` is request-scoped and provider-neutral. It stores:

- raw input
- validated `Agent06Request`
- normalized context
- angle plan
- evidence map
- outline
- drafted sections
- claim review
- generic-content report
- risk report
- quality score
- cost ledger
- status/notes/error state
- final package

State values are primitives or Pydantic models. No cloud SDK clients or provider-native objects are stored in state.

## 7. Output Contract

The terminal contract is `WhitepaperDevelopmentPackage`:

- status
- package id
- request summary
- title options
- recommended angle
- executive summary
- target audience and pain points
- problem statement
- industry/context section
- proposed solution
- benefits
- use cases
- implementation approach
- risks/challenges
- conclusion
- CTA
- key claims and evidence status
- missing evidence
- missing inputs
- risk flags
- generic content flags
- quality score
- improvement suggestions
- cost summary
- notes
- `generation_used_llm`

Every terminal response must be schema-valid, including error and needs-more-input responses.

## 8. Evidence Discipline

The agent must not invent:

- statistics
- citations
- market numbers
- benchmark numbers
- client names
- case-study results
- verified claims
- dates or regulatory facts

Evidence status values:

- `supported_by_user_evidence`
- `user_provided_unverified`
- `needs_evidence`
- `general_reasoning`
- `unsupported`

The package must include a key-claims/evidence table. Any claim that sounds quantified, verified, comparative, regulated, or customer-result-based must have direct supplied evidence or be flagged.

## 9. Generic-Content Detection

Generic output is a first-class quality risk. The detector flags:

- placeholder phrases such as "unlock value", "drive innovation", "seamless solution", or "transform your business" when not tied to specific context
- section text that is too short to be useful
- repeated section wording
- missing company/product/topic terms
- broad benefits without supplied proof or concrete mechanism
- headings with filler paragraphs rather than usable content

Generic content can produce `needs_human` even when all required sections exist.

## 10. Quality Gate

Passing requires:

- quality score >= 80
- no hard-fail risks
- no generic-content hard fail
- every key claim has evidence status
- missing evidence is listed where needed
- output is specific to the supplied company/product/topic
- schema validation passes

Rubric:

- input completeness and constraint handling: 10
- specificity to company/product/topic: 15
- audience and pain-point fit: 10
- whitepaper structure and section completeness: 15
- problem-solution logic and business value: 15
- evidence discipline and claim labeling: 15
- depth, usefulness, and implementation actionability: 10
- tone, clarity, and executive polish: 5
- risk/challenge coverage and review readiness: 5

## 11. Failure Modes

- Missing required inputs -> `needs_more_input`
- Cost gate blocks billable stage -> deterministic fallback and `needs_review_budget_limited`
- Provider failure before usable output -> deterministic fallback where possible, otherwise `error`
- Unsupported/fabricated/generic output -> `needs_human`
- Hard ceiling exceeded or impossible to continue safely -> `stopped_cost_ceiling`

Every path reaches `assemble_package`.

## 12. Local UI

The UI lives in `apps/agent-06-ui/` and follows Agent 05:

- FastAPI + Jinja2
- port 8006
- form posts to `/develop`
- local JSON run storage under `apps/agent-06-ui/runs/`
- `AGENT06_UI_PROVIDER=mock|gcp`
- GCP mode loads `config/gcp.yaml` and calls the shared provider factory
- renders sections, quality score, pass/fail status, missing evidence, risk flags, generic flags, and improvement suggestions

Mock mode remains useful for offline checks. The live path must support GCP through config and the existing provider/core abstraction.

## 13. Tests And Evals

Focused tests:

- schema validation and pass/fail contracts
- prompt trust-boundary wrapping
- deterministic evidence/claim/generic-content helpers
- no cloud SDK imports inside `agent/`
- config overlays load and instantiate correct provider classes
- workflow produces schema-valid terminal packages
- cost ceiling behavior
- UI form + JSON endpoint save runs

Eval stubs:

- complete B2B SaaS input with proof points
- sparse input with missing evidence
- prompt injection in source notes
- invented statistics request
- generic-output risk fixture

## 14. Folder Structure

```
agents/agent-06-whitepaper-development/
  agent/
    __init__.py
    errors.py
    graph.py
    prompts.py
    schemas.py
    scoring.py
    service.py
    state.py
    tools.py
    workflow.py
  config/
    base.yaml
    gcp.yaml
    bedrock.yaml
    azure.yaml
  providers/
    __init__.py
  tests/
    unit/
    integration/
    evals/
    smoke/
  AGENT_SPEC.md
  DESIGN.md
  Dockerfile
  README.md
  RUNBOOK.md
```

```
apps/agent-06-ui/
  app.py
  templates/
  static/
  tests/
  README.md
```

## 15. Design Approval Checklist

- [x] Required workflow stages defined.
- [x] Typed state and terminal output defined.
- [x] Provider-neutral architecture defined.
- [x] Live GCP path required through config/core abstraction.
- [x] Bedrock/Azure stubs preserved.
- [x] Evidence and anti-fabrication rules defined.
- [x] Generic-content detection defined as a gate.
- [x] Cost gate defined.
- [x] Quality/eval approach defined.
- [x] UI behavior defined.

Implementation may proceed against this design.
