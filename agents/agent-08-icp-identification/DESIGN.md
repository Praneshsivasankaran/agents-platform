# Agent 08 - ICP Identification Agent Design

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-08-icp-identification/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## v1 Architecture Note — Shared Demand Generation Engine

The detailed node / tool / contract design below is the target shape. v1
implements it on a shared Demand Generation engine (`packages/demand_generation`)
— a common LangGraph workflow (intake_request -> analyze_context -> generate ->
score_quality -> assemble_package), cost gate, telemetry, risk detection, and
quality scoring — parameterized per agent by a **profile** plus this agent's own
**config overlays**, **schemas**, **prompts**, **scoring dimensions**, **risk
rules**, and **evals**. The deterministic domain logic unique to this agent today
is evidence-backed ICP fit signals and disqualifier flagging; remaining recommendation content is produced by the model under the
agent's prompt and validated deterministically.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Purpose

Agent 08 designs evidence-aware Ideal Customer Profiles for demand generation planning. It must turn supplied GTM context into ranked ICP profiles while preserving the platform pattern: LangGraph orchestration, typed Pydantic contracts, deterministic validation/scoring, `LLMProvider` model calls, request-scoped state, cost gating, eval gates, and cloud-neutral telemetry.

## 2. Agent Boundaries

In scope:

- Analyze user-provided product, customer, sales, and market context.
- Produce ICP profiles, fit criteria, disqualifiers, buying committee guidance, evidence maps, and downstream handoff notes.
- Flag weak evidence, non-compliant criteria, and missing context.

Out of scope:

- Web search, scraping, account enrichment, or contact discovery.
- CRM writes, ad platform writes, audience uploads, or campaign activation.
- Vector retrieval or long-term account memory.
- Automated legal, compliance, or market-size certification.

## 3. Workflow Overview

```text
1. intake_request
2. normalize_gtm_context
3. validate_evidence_sufficiency
4. extract_fit_signals
5. generate_candidate_icps
6. rank_and_merge_icps
7. build_buying_committee_map
8. create_disqualifiers_and_guardrails
9. produce_downstream_handoff
10. validate_claims_and_compliance
11. score_icp_quality
12. assemble_icp_package
13. finalize_response
```

Key difference from content agents: the central task is not drafting prose. It is evidence classification, profile design, and confidence-rated targeting guidance.

## 4. State Model

Request-scoped state should contain:

- request metadata and normalized business context
- supplied customer examples and source-note inventory
- evidence sufficiency report
- extracted positive fit signals and negative fit signals
- candidate ICP profiles
- merged/ranked ICP profiles
- buying committee map
- disqualifiers and targeting guardrails
- compliance and risk flags
- downstream handoff object
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain provider SDK objects, CRM clients, or raw provider responses.

## 5. Inputs

Primary input concepts:

- business context: product, market, geography, pricing, sales motion
- customer evidence: best-fit examples, poor-fit examples, win/loss notes
- GTM constraints: target industries, excluded markets, compliance limits
- optional source notes: sales call summaries, positioning docs, internal research
- desired output depth and maximum cost override within config limits

All inputs are direct context. There is no external data fetch in v1.

## 6. Outputs

Primary output concepts:

- `ICPIdentificationPackage`
- ranked `ICPProfile` records
- fit criteria and disqualifier lists
- buying committee roles
- pain/value/trigger maps
- evidence map and assumption register
- downstream handoff notes for Agents 09-13
- quality report, risk flags, cost summary, and status

The package must be directly renderable later inside MarketingIQ Studio without requiring a standalone UI.

## 7. Pydantic Contract Concepts

Future implementation should define immutable, schema-valid contracts such as:

- `ICPIdentificationRequest`
- `BusinessContext`
- `CustomerEvidenceItem`
- `FitSignal`
- `Disqualifier`
- `BuyingCommitteeRole`
- `ICPProfile`
- `EvidenceMap`
- `AssumptionRegister`
- `DemandGenHandoff`
- `ICPQualityReport`
- `CostUsage`
- `ICPIdentificationPackage`

Contracts should reuse shared `RiskFlag`, `EvidenceItem`, `QualityReport`, and `CostUsage` concepts if the batch implementation abstracts them.

## 8. Tool Requirements

Only local deterministic tools are required in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_icp_inputs` | Normalized request | Missing fields, sufficiency score, hard-fail reasons | None | Local only |
| `extract_fit_signal_candidates` | Source notes and customer examples | Fit/negative signals with source refs | None | Local only |
| `merge_duplicate_icps` | Candidate profiles | Deduplicated profile set | None | Local only |
| `check_targeting_compliance` | Fit criteria and disqualifiers | Protected-attribute and compliance flags | None | Local only |
| `score_icp_package` | Profiles, evidence, risks | Quality report | None | Local only |
| `estimate_cost_usage` | Provider usage metadata | Cost ledger | None | Local only |

No CRM, enrichment, web, data warehouse, or ad platform tool is allowed in v1.

## 9. Memory Requirements

- Request-scoped LangGraph state only.
- No vector store and no persistent ICP memory in v1.
- Optional saved artifacts must use `ObjectStorage` and must be scoped to the current tenant/user.
- Past ICPs can be supplied as direct context by the user, not retrieved autonomously.

## 10. Validation Strategy

- Require a product/service description and at least one market or customer evidence source.
- Flag insufficient evidence rather than inventing precision.
- Reject or hard-flag protected-attribute targeting, discriminatory criteria, and instructions to scrape/enrich accounts.
- Verify every recommended ICP has fit criteria, disqualifiers, evidence, and confidence.
- Ensure downstream handoff fields are present for pass cases.

## 11. Quality Scoring Strategy

Agent 08 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Evidence strength and traceability | 20 |
| ICP specificity without overfitting | 15 |
| Actionable firmographic/operational criteria | 15 |
| Disqualifiers and guardrails | 10 |
| Buying committee clarity | 10 |
| Pain/value/trigger usefulness | 10 |
| Compliance and protected-attribute safety | 10 |
| Downstream handoff readiness | 5 |
| Clarity and executive usability | 5 |

Pass if score >= 82 and no hard-fail flags.

## 12. Evaluation Strategy

Eval datasets should cover strong evidence, sparse evidence, conflicting evidence, overbroad ICP requests, protected-attribute requests, and prompt injection in source notes.

CI gates:

- schema_valid = 100%
- protected_attribute_safety = 100%
- cost_under_ceiling = 100%
- evidence_traceability_rate >= 90%
- pass_rate on complete-input cases >= 80%

## 13. Error Handling Strategy

- Missing required context returns `needs_human` with missing-input warnings.
- Cost guard failure returns `stopped_cost_ceiling` with safe partial analysis.
- Provider failure after bounded retries returns `error` with redacted provider category only.
- Conflicting evidence returns `needs_human` unless the agent can produce explicitly competing ICP hypotheses.
- Compliance hard-fails prevent a passing status.

## 14. Telemetry Requirements

Emit through `Telemetry` only:

- request id, tenant/user-safe labels, provider key, and model tier
- per-node spans for normalization, evidence extraction, generation, validation, scoring, and finalization
- token and cost metrics by stage
- evidence sufficiency score, quality score, profile count, risk flag counts, and terminal status
- no raw customer names, source notes, revenue data, or PII in logs

## 15. Cloud Agnostic Review

- `agent/` imports only local modules and platform interfaces.
- Model calls go through `LLMProvider`.
- Storage goes through `ObjectStorage` if persistence is enabled.
- Secrets go through `SecretStore`.
- Observability goes through `Telemetry`.
- No `google.cloud`, `vertexai`, `boto3`, `botocore`, Azure SDK, CRM SDK, enrichment SDK, direct model SDK, or `litellm` import is allowed inside `agent/`.
- GCP, Bedrock, and Azure behavior is selected by config overlays.

## 16. Future Integration Considerations

- MarketingIQ Studio should render ICP profiles as reusable Demand Generation strategy objects.
- Agent 09 should accept the ICP package as direct structured input.
- Agent 11 should reuse fit signals and disqualifiers for scoring concepts.
- Future CRM/account-list integrations require a separate provider/tool design and HITL write approvals.
- Future market sizing or enrichment should be added through provider abstractions, not inline SDK calls.

