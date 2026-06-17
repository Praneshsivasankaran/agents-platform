# Agent 09 - Audience Segmentation Agent Design

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-09-audience-segmentation/`
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
is audience-size guarding (size estimates require supplied counts) and segment/suppression rule clarity; remaining recommendation content is produced by the model under the
agent's prompt and validated deterministically.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Purpose

Agent 09 turns ICP and campaign context into actionable audience segments. The design must support precise segmentation without external audience activation, while following the shared platform pattern: LangGraph, Pydantic contracts, deterministic validation/scoring, `LLMProvider`, request-scoped state, cost gates, eval gates, and `Telemetry`.

## 2. Agent Boundaries

In scope:

- Produce audience segment definitions and campaign-use guidance from supplied context.
- Detect segment overlap, thin data, compliance risks, and suppression needs.
- Prepare structured handoffs for lead generation, scoring, recommendation, and nurture agents.

Out of scope:

- Audience uploads, CRM/MAP writes, ad platform writes, or lead routing.
- Contact enrichment, list purchase, web search, scraping, or data warehouse queries.
- Long-term audience memory or vector retrieval.
- Automated compliance certification.

## 3. Workflow Overview

```text
1. intake_request
2. normalize_icp_and_campaign_context
3. inventory_available_audience_fields
4. validate_segmentation_feasibility
5. derive_segmentation_axes
6. generate_candidate_segments
7. check_overlap_and_merge_segments
8. assign_messaging_and_channel_fit
9. apply_suppression_and_compliance_rules
10. create_downstream_handoff
11. score_segmentation_quality
12. assemble_segmentation_package
13. finalize_response
```

The workflow differs from Agent 08 by focusing on campaign-specific partitioning, not defining the strategic ICP itself.

## 4. State Model

Request-scoped state should contain:

- request metadata
- normalized ICP summary
- campaign objective and offer context
- available audience fields inventory
- feasibility report
- segmentation axes
- candidate and merged segments
- overlap report
- suppression/compliance flags
- messaging/channel fit map
- downstream handoff object
- quality report, cost ledger, status, and final package

State must stay provider-neutral and JSON-serializable.

## 5. Inputs

Primary input concepts:

- ICP package or ICP summary
- campaign goal, offer, funnel stage, and region
- available audience/account attributes
- source audience notes or list summary
- exclusion and suppression requirements
- consent/compliance constraints
- optional prior performance summaries as direct context

## 6. Outputs

Primary output concepts:

- `AudienceSegmentationPackage`
- `AudienceSegment` records with inclusion/exclusion rules
- overlap and thin-data warnings
- segment messaging and channel-fit guidance
- suppression/compliance notes
- field requirements for Marketing Ops
- downstream handoff notes
- quality report, risk flags, cost summary, and status

## 7. Pydantic Contract Concepts

Future contracts should include:

- `AudienceSegmentationRequest`
- `CampaignContext`
- `AudienceFieldInventory`
- `SegmentationAxis`
- `AudienceSegment`
- `SegmentRule`
- `OverlapReport`
- `SuppressionRule`
- `SegmentMessagingGuide`
- `SegmentationQualityReport`
- `DemandGenHandoff`
- `AudienceSegmentationPackage`

Shared concepts should be reused for risk flags, evidence items, cost usage, and terminal status.

## 8. Tool Requirements

Only local deterministic tools are required in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_segmentation_inputs` | Request and field inventory | Missing fields, feasibility score, hard-fail reasons | None | Local only |
| `score_segment_overlap` | Candidate segments | Overlap matrix and merge suggestions | None | Local only |
| `detect_thin_segments` | Segments and field availability | Thin/low-confidence warnings | None | Local only |
| `check_suppression_rules` | Segment rules and constraints | Compliance/suppression flags | None | Local only |
| `score_segmentation_package` | Segments, risks, handoff | Quality report | None | Local only |
| `estimate_cost_usage` | Provider usage metadata | Cost ledger | None | Local only |

No activation, CRM, MAP, warehouse, enrichment, web, or ad-platform tool is allowed in v1.

## 9. Memory Requirements

- Request-scoped state only.
- No persistent audience memory in v1.
- Past campaign performance can be supplied by the user as direct context.
- Optional artifact persistence must use `ObjectStorage` and tenant-scoped keys.

## 10. Validation Strategy

- Require an ICP/target audience and campaign objective.
- Require at least one available segmentation attribute or return `needs_human`.
- Validate each segment has inclusion rules, exclusion rules, rationale, and usage guidance.
- Flag overlapping, tiny, broad, or unmeasurable segments.
- Hard-flag protected-attribute segmentation and consent/suppression violations.
- Ensure all pass outputs include downstream handoff guidance.

## 11. Quality Scoring Strategy

Agent 09 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Segment distinctness and non-overlap | 20 |
| Inclusion/exclusion rule clarity | 15 |
| Campaign objective alignment | 15 |
| Persona/pain/message relevance | 15 |
| Data availability and feasibility | 10 |
| Suppression and compliance handling | 10 |
| Downstream handoff readiness | 10 |
| Clarity and operational usability | 5 |

Pass if score >= 82 and no hard-fail flags.

## 12. Evaluation Strategy

Eval datasets should cover complete ICP-to-segment requests, sparse data, overlapping segments, consent constraints, region-specific exclusions, protected-attribute attempts, and prompt injection in notes.

CI gates:

- schema_valid = 100%
- protected_attribute_safety = 100%
- consent_constraint_preserved = 100%
- segment_rule_completeness >= 90%
- pass_rate on complete-input cases >= 80%
- cost_under_ceiling = 100%

## 13. Error Handling Strategy

- Missing ICP or campaign goal returns `needs_human`.
- Inadequate segmentation fields returns `needs_human` with field recommendations.
- Protected-attribute requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with safe partial output.
- Provider failure returns `error` with redacted failure category and preserved incurred cost.

## 14. Telemetry Requirements

Emit through `Telemetry` only:

- request id, provider key, model tier, and terminal status
- spans for normalization, feasibility, segment generation, overlap checking, suppression validation, scoring, and finalization
- token and cost metrics per billable stage
- segment count, overlap count, suppression count, quality score, risk flag counts
- no raw lead names, account records, or PII in logs

## 15. Cloud Agnostic Review

- All model calls go through `LLMProvider`.
- No SDK imports for GCP, Vertex, AWS, Azure, CRM, MAP, data warehouse, enrichment, ad platforms, direct model providers, or `litellm` inside `agent/`.
- Optional persistence uses `ObjectStorage`; secrets use `SecretStore`; observability uses `Telemetry`.
- Provider selection is entirely config-driven.
- Bedrock and Azure overlays must remain structurally compatible with GCP-first implementation.

## 16. Future Integration Considerations

- MarketingIQ Studio should let users pass Agent 08 ICP output directly into Agent 09.
- Agent 10 should consume segment definitions for lead generation planning.
- Agent 11 should consume segment rules for scoring explainability.
- Agent 13 should consume segment pain/message guidance for nurture journey planning.
- Future audience uploads require HITL, audit, and platform-specific provider/tool design outside this v1 agent.

