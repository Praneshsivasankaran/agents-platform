# Agent 13 - Lead Nurturing Agent Design

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-13-lead-nurturing/`
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
is journey trigger / exit / suppression and consent planning; remaining recommendation content is produced by the model under the
agent's prompt and validated deterministically.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Purpose

Agent 13 designs compliant, segment-aware lead nurture journeys from supplied audience, scoring, campaign, content, and sales handoff context. It must produce automation-ready planning artifacts without performing automation.

## 2. Agent Boundaries

In scope:

- Design journey branches, touchpoints, cadence, triggers, exits, suppression, and handoff rules.
- Recommend content and personalization themes.
- Flag content gaps, consent risks, cadence risks, and sales-handoff ambiguity.

Out of scope:

- Sending email/SMS/messages.
- Writing marketing automation workflows.
- CRM/MAP updates, audience mutations, or ad retargeting activation.
- Contact enrichment, scraping, or live engagement reads.

## 3. Workflow Overview

```text
1. intake_request
2. normalize_journey_context
3. validate_nurture_readiness
4. map_segments_and_score_bands
5. define_journey_objectives
6. generate_touchpoint_sequence
7. assign_content_and_message_themes
8. define_triggers_exits_suppression
9. create_sales_handoff_rules
10. validate_cadence_consent_and_content_gaps
11. score_nurture_quality
12. assemble_nurture_package
13. finalize_response
```

This workflow is journey-logic-first: branching, timing, constraints, and handoff rules matter more than long-form copy.

## 4. State Model

Request-scoped state should contain:

- normalized segments, score bands, campaign context, and content inventory
- nurture readiness report
- journey objectives
- branch map by segment/score/lifecycle stage
- touchpoint sequence
- content and message theme assignments
- trigger, exit, suppression, and handoff rules
- content gap and compliance reports
- quality report, cost ledger, terminal status, and final package

State must remain serializable and cloud-neutral.

## 5. Inputs

Primary input concepts:

- audience segment package
- score bands or qualification rules
- campaign/offer context
- content inventory
- lifecycle stage and desired cadence
- consent, suppression, and regional constraints
- sales follow-up expectations

## 6. Outputs

Primary output concepts:

- `LeadNurturingPackage`
- journey map and branch definitions
- touchpoint plan
- content assignment and gap list
- personalization guide
- trigger/exit/suppression rules
- sales handoff rules
- KPI and experiment plan
- quality report, risk flags, cost summary, and status

## 7. Pydantic Contract Concepts

Future contracts should include:

- `LeadNurturingRequest`
- `NurtureJourney`
- `JourneyBranch`
- `Touchpoint`
- `CadenceRule`
- `ContentAssignment`
- `ContentGap`
- `TriggerRule`
- `ExitRule`
- `SuppressionRule`
- `SalesHandoffRule`
- `NurtureQualityReport`
- `LeadNurturingPackage`

Shared `AudienceSegment`, `ScoreBand`, `RiskFlag`, `CostUsage`, and `DemandGenHandoff` concepts should be reused.

## 8. Tool Requirements

Local deterministic tools:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_nurture_inputs` | Segments, score bands, content, constraints | Readiness report | None | Local only |
| `check_cadence_limits` | Touchpoint sequence | Spam/cadence warnings | None | Local only |
| `check_content_coverage` | Journey and inventory | Content gap list | None | Local only |
| `check_consent_and_suppression` | Journey rules and constraints | Compliance flags | None | Local only |
| `score_nurture_package` | Journey, gaps, risks | Quality report | None | Local only |
| `estimate_cost_usage` | Provider usage metadata | Cost ledger | None | Local only |

No email, MAP, CRM, SMS, ad, enrichment, or publishing tool is allowed in v1.

## 9. Memory Requirements

- Request-scoped state only.
- No persistent lead journey memory in v1.
- Existing journeys can be pasted as direct context.
- Optional artifact persistence must use `ObjectStorage`.

## 10. Validation Strategy

- Require segment or audience context, journey objective, and at least basic content/offer context.
- Flag missing score bands, cadence, content inventory, consent rules, or sales handoff.
- Hard-flag requests to send messages or write automation.
- Validate every pass journey has triggers, exits, suppression, touchpoints, KPI plan, and owner/handoff notes.
- Check cadence against configured maximums.

## 11. Quality Scoring Strategy

Agent 13 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Journey logic and branch clarity | 20 |
| Segment and score-band alignment | 15 |
| Content relevance and gap handling | 15 |
| Cadence and timing quality | 10 |
| Personalization usefulness | 10 |
| Consent/suppression/compliance handling | 10 |
| Sales handoff and lifecycle actionability | 10 |
| KPI and experiment clarity | 5 |
| Operational clarity | 5 |

Pass if score >= 82 and no hard-fail flags.

## 12. Evaluation Strategy

Eval datasets should cover post-event nurture, low-score nurture, high-score sales handoff, missing content, consent constraints, cadence abuse, prompt injection, and send/activation requests.

CI gates:

- schema_valid = 100%
- no_send_or_activation_behavior = 100%
- consent_preserved = 100%
- journey_completeness >= 85%
- content_gap_detection >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 13. Error Handling Strategy

- Missing journey objective or segment context returns `needs_human`.
- Send/automation-write request returns hard-fail flags.
- Missing content returns `needs_human` or pass with content-gap warnings depending on severity.
- Cost stop returns `stopped_cost_ceiling`.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 14. Telemetry Requirements

Emit through `Telemetry` only:

- request id, provider, model tier, terminal status
- spans for validation, journey mapping, touchpoint generation, content assignment, compliance checks, scoring, and finalization
- token/cost metrics by stage
- journey branch count, touchpoint count, content gap count, risk flag count, quality score
- no raw lead data, email addresses, or sensitive notes in logs

## 15. Cloud Agnostic Review

- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`; telemetry through `Telemetry`.
- No cloud SDK, CRM/MAP/email/SMS/ad SDK, direct model SDK, or `litellm` inside `agent/`.
- Provider behavior must be selected only by config overlays.

## 16. Future Integration Considerations

- MarketingIQ Studio should render journeys visually and support human editing before export.
- Future MAP export requires a separate provider/tool design, HITL, audit, and rollback behavior.
- Agent 11 score bands should drive branch logic.
- Agent 14 should measure downstream conversion and nurture effectiveness.
- Agent 02 may later repurpose approved nurture messaging into channel-specific drafts, but this agent should not directly import another agent.

