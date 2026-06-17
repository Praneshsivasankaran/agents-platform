# Agent 10 - Lead Generation Agent Design

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-10-lead-generation/`
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
is capture-path and landing-page/form blueprint planning, with contact-list generation and purchased-list requests refused; remaining recommendation content is produced by the model under the
agent's prompt and validated deterministically.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Purpose

Agent 10 creates a structured lead generation campaign blueprint from approved ICP, segmentation, offer, and constraint inputs. It must prepare the campaign for human execution planning while keeping v1 draft-only and provider-neutral.

## 2. Agent Boundaries

In scope:

- Recommend lead generation motions and capture mechanics.
- Define offer, landing page, form, qualification, channel, KPI, and experiment guidance.
- Produce handoff notes for scoring, campaign recommendation, and nurture agents.

Out of scope:

- Contact scraping, enrichment, list buying, or autonomous lead discovery.
- CRM/MAP/ad-platform writes or audience uploads.
- Publishing landing pages, sending emails, or activating campaigns.
- Budget optimization based on live ad inventory.

## 3. Workflow Overview

```text
1. intake_request
2. normalize_campaign_context
3. validate_campaign_readiness
4. map_icp_segments_to_goal
5. select_candidate_lead_gen_motions
6. design_offer_and_capture_path
7. create_landing_page_and_form_brief
8. define_qualification_and_handoff_rules
9. build_channel_and_experiment_plan
10. validate_consent_scope_and_feasibility
11. score_blueprint_quality
12. assemble_lead_generation_package
13. finalize_response
```

The workflow is campaign-architecture oriented, not content drafting and not lead-record generation.

## 4. State Model

Request-scoped state should contain:

- request metadata and normalized campaign context
- ICP/segment summary
- readiness report
- selected lead generation motions
- offer and capture-path plan
- landing page/form brief
- qualification criteria
- channel plan and experiment plan
- consent/compliance/risk flags
- downstream handoff object
- quality report, cost ledger, terminal status, and final package

State must remain plain typed data with no external SDK clients or provider objects.

## 5. Inputs

Primary input concepts:

- ICP and audience segment packages
- campaign objective and funnel stage
- offer, product/service, channel preferences, timeline, and budget
- existing assets and landing page constraints
- qualification criteria and sales follow-up assumptions
- consent, suppression, and regional constraints
- optional past performance summaries as direct context

## 6. Outputs

Primary output concepts:

- `LeadGenerationPackage`
- campaign motion recommendation
- target segment mapping
- offer and lead magnet plan
- landing page brief
- form and consent field recommendations
- qualification and scoring handoff
- channel plan, KPI plan, experiment plan
- risks, missing inputs, quality report, cost summary, and status

## 7. Pydantic Contract Concepts

Future contracts should include:

- `LeadGenerationRequest`
- `CampaignGoal`
- `OfferContext`
- `LeadGenerationMotion`
- `CapturePath`
- `LandingPageBrief`
- `FormFieldRecommendation`
- `QualificationRule`
- `ChannelPlan`
- `ExperimentPlan`
- `LeadScoringHandoff`
- `LeadGenerationQualityReport`
- `LeadGenerationPackage`

Shared `RiskFlag`, `EvidenceItem`, `CostUsage`, and `DemandGenHandoff` contracts should be reused if abstracted in the batch.

## 8. Tool Requirements

Only local deterministic tools are required in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_campaign_readiness` | Campaign context | Missing fields, readiness score, blockers | None | Local only |
| `match_motion_to_funnel_stage` | Goal, segment, offer | Candidate motions and rationale | None | Local only |
| `check_capture_path_completeness` | Offer, landing page, form | Completeness warnings | None | Local only |
| `check_consent_and_suppression` | Form plan, region, constraints | Risk flags | None | Local only |
| `score_lead_gen_blueprint` | Blueprint, risks, handoffs | Quality report | None | Local only |
| `estimate_cost_usage` | Provider usage metadata | Cost ledger | None | Local only |

No external system tool is allowed in v1.

## 9. Memory Requirements

- Request-scoped state only.
- No long-term campaign memory in v1.
- Prior campaign performance may be supplied as direct context only.
- Optional artifact persistence must use `ObjectStorage`.

## 10. Validation Strategy

- Require a campaign goal, target audience/segment, offer or offer objective, and funnel stage.
- Flag missing budget, timeline, follow-up, landing page, or consent constraints.
- Reject requests to scrape contacts, enrich leads, or activate campaigns.
- Verify pass outputs include capture path, qualification rules, KPIs, and downstream handoff.
- Preserve consent/suppression constraints as hard requirements.

## 11. Quality Scoring Strategy

Agent 10 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| ICP and segment alignment | 20 |
| Offer and channel fit | 15 |
| Funnel and capture-path completeness | 15 |
| Landing page and form clarity | 10 |
| Qualification and scoring handoff | 10 |
| Experiment and KPI design | 10 |
| Operational feasibility | 10 |
| Consent/compliance handling | 5 |
| Executive clarity | 5 |

Pass if score >= 82 and no hard-fail flags.

## 12. Evaluation Strategy

Eval datasets should include complete lead generation briefs, weak offers, missing sales follow-up, low-budget constraints, consent restrictions, prompt injection, and forbidden contact scraping requests.

CI gates:

- schema_valid = 100%
- no_external_activation = 100%
- consent_preserved = 100%
- capture_path_completeness >= 85%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 13. Error Handling Strategy

- Missing campaign goal or target audience returns `needs_human`.
- Forbidden scraping/enrichment/activation request returns hard-fail risk flags.
- Weak offer or missing follow-up returns `needs_human` unless safe recommendations can be produced with warnings.
- Cost guard returns `stopped_cost_ceiling`.
- Provider failure returns `error` with redacted category and preserved cost ledger.

## 14. Telemetry Requirements

Emit through `Telemetry` only:

- request id, provider, model tier, terminal status
- spans for readiness validation, motion selection, capture design, qualification design, validation, scoring, and finalization
- stage token/cost metrics
- selected motion, segment count, risk flag count, score, and status as low-cardinality fields
- no raw lead data, budgets, pasted notes, or sensitive campaign context in logs

## 15. Cloud Agnostic Review

- Model calls only through `LLMProvider`.
- Optional storage only through `ObjectStorage`.
- Secrets only through `SecretStore`.
- Telemetry only through `Telemetry`.
- No cloud SDK, CRM/MAP/ad-platform SDK, enrichment SDK, scraping library, direct model SDK, or `litellm` inside `agent/`.
- Provider swap must be config-only across GCP, Bedrock, and Azure.

## 16. Future Integration Considerations

- MarketingIQ Studio should ingest Agent 08/09 outputs and render the blueprint as a campaign planning object.
- Agent 11 should consume qualification rules and scoring handoff.
- Agent 13 should consume the offer, segments, and nurture-stage assumptions.
- Agent 14 should later analyze performance against the KPI plan.
- Future activation requires separate tools, least-privilege write scopes, HITL, and audit trails.

