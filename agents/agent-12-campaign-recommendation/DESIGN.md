# Agent 12 - Campaign Recommendation Agent Design

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-12-campaign-recommendation/`
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
is ranked campaign-option planning with budget and dependency rationale; remaining recommendation content is produced by the model under the
agent's prompt and validated deterministically.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Purpose

Agent 12 ranks and explains campaign recommendations from supplied audience, objective, budget, channel, asset, and performance context. Its main output is a decision package for human campaign planning, not live campaign execution.

## 2. Agent Boundaries

In scope:

- Generate and rank campaign play options.
- Recommend audience, channel, budget, asset, KPI, and experiment plan.
- Flag feasibility, dependency, compliance, and budget risks.

Out of scope:

- Campaign activation, ad spend, email send, audience upload, or publishing.
- Live channel optimization or analytics reads.
- Autonomous market research, scraping, or competitor monitoring.
- Financial forecasting beyond planning estimates.

## 3. Workflow Overview

```text
1. intake_request
2. normalize_goal_and_constraints
3. summarize_audience_and_assets
4. validate_recommendation_readiness
5. generate_campaign_play_options
6. score_options_against_constraints
7. rank_recommendations
8. build_primary_campaign_plan
9. create_kpi_and_experiment_plan
10. identify_dependencies_and_risks
11. score_recommendation_quality
12. assemble_campaign_recommendation_package
13. finalize_response
```

This workflow centers on comparative decision support: option generation, constraint scoring, and ranked recommendation.

## 4. State Model

Request-scoped state should contain:

- normalized campaign objective, budget, timeline, region, and channel constraints
- ICP/segment summary
- asset and offer inventory
- readiness report
- candidate campaign plays
- option scores and ranking rationale
- primary recommendation plan
- KPI/experiment plan
- dependency and risk register
- downstream handoff object
- quality report, cost ledger, status, and final package

## 5. Inputs

Primary input concepts:

- ICP and audience segments
- campaign objective, funnel stage, target metric, and budget
- channel availability and operational constraints
- offer/content/asset inventory
- direct-context performance summaries
- compliance and approval requirements

## 6. Outputs

Primary output concepts:

- `CampaignRecommendationPackage`
- ranked `CampaignOption` records
- primary recommendation and alternatives
- channel mix and budget guidance
- asset/content requirements
- KPI and experiment plan
- operational dependency checklist
- risk flags, quality report, cost summary, and status

## 7. Pydantic Contract Concepts

Future contracts should include:

- `CampaignRecommendationRequest`
- `CampaignObjective`
- `CampaignConstraintSet`
- `AssetInventory`
- `CampaignOption`
- `OptionScore`
- `ChannelMixRecommendation`
- `BudgetGuidance`
- `KPIPlan`
- `ExperimentDesign`
- `DependencyChecklist`
- `CampaignRecommendationQualityReport`
- `CampaignRecommendationPackage`

Shared `AudienceSegment`, `RiskFlag`, `EvidenceItem`, `CostUsage`, and `DemandGenHandoff` concepts should be reused where possible.

## 8. Tool Requirements

Local deterministic tools:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_recommendation_readiness` | Request | Missing constraints and blockers | None | Local only |
| `score_campaign_option` | Option, goal, audience, constraints | Dimension scores and rationale | None | Local only |
| `normalize_budget_split` | Channel plan and budget | Budget allocation checks | None | Local only |
| `check_dependency_completeness` | Recommendation | Missing operational dependencies | None | Local only |
| `score_recommendation_package` | Ranked plan, risks | Quality report | None | Local only |
| `estimate_cost_usage` | Provider usage metadata | Cost ledger | None | Local only |

No ad, CRM, MAP, analytics, warehouse, or publishing tool is allowed in v1.

## 9. Memory Requirements

- Request-scoped state only.
- No persistent campaign-performance memory in v1.
- Past performance summaries are direct context only.
- Optional package persistence uses `ObjectStorage`.

## 10. Validation Strategy

- Require objective, target audience, funnel stage, timeline, and at least one constraint.
- Flag missing budget, channel availability, assets, or KPI target.
- Ensure each ranked option has rationale, risks, and basic KPI logic.
- Hard-flag automatic activation or spend requests.
- Preserve consent, regional, and brand constraints.

## 11. Quality Scoring Strategy

Agent 12 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Goal and audience fit | 20 |
| Channel recommendation rationale | 15 |
| Budget and timeline practicality | 15 |
| Offer/content/asset alignment | 10 |
| KPI and experiment design | 10 |
| Dependency and operational readiness | 10 |
| Risk/compliance handling | 10 |
| Ranking clarity and executive usability | 10 |

Pass if score >= 82 and no hard-fail flags.

## 12. Evaluation Strategy

Eval datasets should cover complete recommendation requests, budget constraints, missing assets, channel conflict, weak performance history, compliance-constrained regions, prompt injection, and activation requests.

CI gates:

- schema_valid = 100%
- no_activation_behavior = 100%
- dependency_detection >= 90%
- recommendation_rationale_score >= 85
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 13. Error Handling Strategy

- Missing objective or audience returns `needs_human`.
- Automatic activation/spend requests return hard-fail flags.
- Conflicting constraints return `needs_human` unless options can be safely ranked with warnings.
- Cost stop returns `stopped_cost_ceiling`.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 14. Telemetry Requirements

Emit through `Telemetry` only:

- request id, provider, model tier, terminal status
- spans for readiness, option generation, option scoring, ranking, KPI planning, dependency checking, quality scoring, and finalization
- token/cost metrics per billable stage
- option count, selected play type, dependency count, risk count, quality score
- no raw budget details, pasted performance notes, or sensitive campaign data in logs

## 15. Cloud Agnostic Review

- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`; telemetry through `Telemetry`.
- No cloud SDKs, ad-platform SDKs, CRM/MAP SDKs, analytics SDKs, direct model SDKs, or `litellm` inside `agent/`.
- GCP, Bedrock, and Azure are selected by config overlays only.

## 16. Future Integration Considerations

- MarketingIQ Studio should show ranked campaign options and allow human selection before implementation.
- Agent 10 can consume a selected recommendation to create a detailed lead generation blueprint.
- Agent 13 can consume the selected campaign plan for nurture design.
- Agent 14 can later compare actual conversion outcomes with the KPI plan.
- Future optimization loops require separate live analytics and activation designs with HITL gates.

