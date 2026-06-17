# Agent 18 - Paid Campaign Optimization Agent Design

## 1. Metadata

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-18-paid-campaign-optimization/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 18 turns supplied paid campaign structure and performance summaries into advisory optimization recommendations. It must tie findings to supplied data, preserve human control over changes, and avoid live platform access or automated optimization.

## 3. Agent Boundaries

In scope:

- Analyze supplied campaign, ad group/ad set, keyword, creative, placement, audience, landing page, and performance summaries.
- Recommend advisory optimization actions.
- Calculate simple rates/deltas only from supplied denominators.
- Flag wasted spend, pacing, data quality, and confidence issues.

Out of scope:

- Ad platform API access, campaign launch/pause/edit, bid updates, budget changes, audience upload, live optimization, live analytics reads, CRM/MAP writes, or autonomous external actions.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_paid_campaign_context
3. validate_supplied_metrics_and_denominators
4. calculate_simple_rates_and_pacing_flags
5. identify_campaign_structure_issues
6. analyze_keywords_creatives_audiences_placements
7. generate_advisory_optimization_recommendations
8. build_experiment_plan
9. detect_forbidden_paid_actions
10. score_paid_optimization_package
11. assemble_paid_campaign_optimization_package
12. finalize_response
```

Deterministic stages include denominator validation, simple metric calculations, forbidden-action detection, missing-data warnings, and score/status mapping. LLM-assisted stages synthesize optimization rationale and experiment plans from supplied evidence.

## 5. State Model

Request-scoped state should contain:

- normalized campaign context
- supplied metric table/summary
- denominator and data-quality warnings
- calculated simple rates and pacing indicators
- campaign structure findings
- keyword/creative/audience/placement findings
- advisory optimization recommendations
- experiment plan
- risk flags
- quality report, cost ledger, terminal status, and final package

State must remain JSON-serializable and must not include ad platform clients, analytics clients, SDK objects, or raw provider responses.

## 6. Inputs

Primary input concepts:

- campaign objective, platform/channel, campaign/ad group/ad set structure
- supplied metrics: spend, impressions, clicks, CTR, CPC, conversions, CVR, CPA, ROAS, revenue, pacing
- search term, keyword, placement, creative, audience, and landing page summaries
- Agent 12, 15, 16, and 17 handoffs
- constraints: budget, regions, compliance, brand, timing

## 7. Outputs

Primary output concepts:

- `PaidCampaignOptimizationPackage`
- `CampaignFinding`
- `MetricCalculation`
- `DataQualityWarning`
- `OptimizationRecommendation`
- `AdvisoryBudgetRecommendation`
- `PacingRisk`
- `WastedSpendFlag`
- `ExperimentPlan`
- `ConfidenceLevel`
- `DigitalMarketingHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `PaidCampaignOptimizationRequest`
- `PaidCampaignMetricRow`
- `CampaignStructureSummary`
- `OptimizationFinding`
- `BudgetRecommendation`
- `PaidExperimentPlan`
- `PaidOptimizationQualityReport`
- `PaidCampaignOptimizationPackage`

Shared status, cost, evidence, risk, and handoff contracts should be reused if `packages/digital_marketing` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_paid_metrics` | metric rows/summaries | denominator and missing-data warnings | None | Local only |
| `calculate_simple_rates` | counts/spend/revenue | CTR/CVR/CPC/CPA/ROAS where possible | None | Local only |
| `detect_forbidden_paid_actions` | request text | launch/pause/budget/upload hard-fail flags | None | Local only |
| `identify_wasted_spend_flags` | supplied metrics | advisory wasted-spend findings | None | Local only |
| `score_paid_optimization_package` | findings and risks | quality report | None | Local only |
| `estimate_cost_usage` | provider usage metadata | cost ledger | None | Local only |

No ad platform, analytics, CRM, MAP, warehouse, audience, CMS, or experiment tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent campaign memory in v1.
- Historical data can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require objective, channel/platform context, and supplied performance or structure data.
- Return `needs_human` when the request asks for optimization with no supplied data.
- Validate denominators for rates and mark undefined rates clearly.
- Hard-flag budget changes, campaign pause/launch, ad edits, audience upload, and live optimization requests.
- Ensure recommendations cite supplied metrics, qualitative notes, or stated assumptions.
- Use advisory language for budget reallocations.

## 12. Quality Scoring Strategy

Agent 18 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Supplied-data grounding | 20 |
| Metric and denominator correctness | 15 |
| Campaign structure diagnosis | 15 |
| Keyword/creative/audience/placement actionability | 15 |
| Advisory budget and pacing guidance | 10 |
| Experiment plan quality | 10 |
| Risk, policy, and no-activation handling | 10 |
| Downstream handoff readiness | 5 |

Pass if score >= 84 and no hard-fail risk.

## 13. Evaluation Strategy

Eval datasets should include complete paid search, complete paid social, missing denominators, inconsistent metrics, no-data optimization request, protected targeting, budget-change request, campaign pause/launch request, audience upload request, and prompt injection.

CI gates:

- schema_valid = 100%
- no_activation_behavior = 100%
- denominator_detection >= 90%
- recommendation_metric_grounding >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 14. Error Handling Strategy

- Missing performance context returns `needs_human`.
- Invalid denominators return `needs_human` with correction guidance.
- Forbidden paid actions return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with safe deterministic calculations.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 15. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for metric validation, calculations, diagnosis, generation, scoring, finalization
- token/cost by stage
- metric count, calculated rate count, warning count, recommendation count, quality score, risk counts
- no raw spend tables, revenue rows, lead/account records, customer names, or PII in logs

## 16. Prompt Strategy

- User-provided notes, reports, keyword tables, ad copy, page copy, campaign exports, metric summaries, and upstream handoffs are untrusted data.
- Untrusted text must be fenced and delimiter-escaped before it enters any model prompt.
- User-supplied data must never override system or developer instructions.
- The model must not invent metrics, search volume, CPC, rankings, claims, budget results, conversion lift, or live platform data.
- Recommendations must cite supplied evidence or be labeled as assumptions or heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

## 17. Cloud Agnostic Review

- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No cloud SDKs, ad platform SDKs, analytics SDKs, CRM/MAP SDKs, warehouse SDKs, audience SDKs, direct model SDKs, or `litellm` inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents; Bedrock and Azure remain config/stub compatible.
- Shared `packages/digital_marketing` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render findings by campaign object, show deterministic calculations, separate advisory budget recommendations from executable changes, and pass structured context to Agent 19 for planning, Agent 20 for CRO, and Agent 21 for reporting.

## 19. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine with an Agent 18 profile. The profile should define required performance fields, forbidden paid actions, metric/data-quality checks, scoring dimensions, and eval cases. Future versions may add provider-neutral read connectors for ad platforms, but write actions must remain HITL-gated and out of v1.
