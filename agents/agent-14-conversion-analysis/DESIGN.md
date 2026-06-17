# Agent 14 - Conversion Analysis Agent Design

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-14-conversion-analysis/`
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
is deterministic funnel conversion math and denominator-consistency / sample-size checks; remaining recommendation content is produced by the model under the
agent's prompt and validated deterministically.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Purpose

Agent 14 analyzes supplied conversion and funnel data to identify bottlenecks, explain likely causes, and recommend prioritized optimization experiments. It should use deterministic metric math first and model reasoning second.

## 2. Agent Boundaries

In scope:

- Normalize supplied funnel/campaign data.
- Calculate rates, deltas, drop-offs, and comparisons.
- Identify bottlenecks, anomalies, hypotheses, and experiment recommendations.
- Flag data-quality and attribution caveats.

Out of scope:

- Live analytics, CRM, MAP, or ad-platform queries.
- Campaign changes, budget updates, or experiment activation.
- Causal proof or statistical certification.
- Long-term performance memory or automated dashboards in v1.

## 3. Workflow Overview

```text
1. intake_request
2. normalize_metric_context
3. validate_funnel_schema_and_denominators
4. calculate_conversion_rates_and_dropoffs
5. compare_segments_sources_or_periods
6. detect_anomalies_and_data_quality_issues
7. identify_bottleneck_candidates
8. generate_root_cause_hypotheses
9. prioritize_optimization_recommendations
10. create_experiment_backlog
11. score_analysis_quality
12. assemble_conversion_analysis_package
13. finalize_response
```

This workflow is the most metric-heavy Demand Generation agent. Deterministic calculations should be isolated from narrative diagnosis.

## 4. State Model

Request-scoped state should contain:

- normalized metric context and period
- funnel stage definitions
- validated metric table
- deterministic rate/drop-off calculations
- comparison results
- anomaly and data-quality warnings
- bottleneck candidates
- root-cause hypotheses
- prioritized recommendations
- experiment backlog
- quality report, cost ledger, terminal status, and final package

State must stay JSON-serializable and provider-neutral.

## 5. Inputs

Primary input concepts:

- funnel stages and metric counts
- campaign, segment, source, channel, period, and region labels
- KPI plan or target rates from Agents 10/12/13 if available
- benchmarks or previous-period summaries
- qualitative notes and known anomalies
- data-quality or attribution caveats

## 6. Outputs

Primary output concepts:

- `ConversionAnalysisPackage`
- normalized funnel table
- calculated conversion rates and drop-offs
- segment/source/period comparisons
- bottleneck ranking
- root-cause hypotheses
- prioritized recommendations
- experiment backlog and measurement plan
- data-quality warnings, quality report, cost summary, and status

## 7. Pydantic Contract Concepts

Future contracts should include:

- `ConversionAnalysisRequest`
- `FunnelStageMetric`
- `NormalizedFunnel`
- `ConversionRate`
- `SegmentComparison`
- `DataQualityWarning`
- `BottleneckFinding`
- `RootCauseHypothesis`
- `OptimizationRecommendation`
- `ExperimentBacklogItem`
- `ConversionAnalysisQualityReport`
- `ConversionAnalysisPackage`

Shared `RiskFlag`, `EvidenceItem`, `CostUsage`, and `DemandGenHandoff` concepts should be reused where applicable.

## 8. Tool Requirements

Local deterministic tools:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_funnel_metrics` | Funnel rows and stage definitions | Schema, denominator, and missing-stage warnings | None | Local only |
| `calculate_rates_and_dropoffs` | Validated metrics | Conversion rates, deltas, drop-offs | None | Local only |
| `compare_segments_or_periods` | Metric groups | Comparison table and significance warnings | None | Local only |
| `detect_data_quality_issues` | Metrics and notes | Missing, inconsistent, small-sample, attribution warnings | None | Local only |
| `score_conversion_analysis` | Findings, math, risks | Quality report | None | Local only |
| `estimate_cost_usage` | Provider usage metadata | Cost ledger | None | Local only |

No live analytics, CRM, MAP, ad-platform, warehouse, or experiment tool is allowed in v1.

## 9. Memory Requirements

- Request-scoped state only.
- No persistent performance memory in v1.
- Historical data can be supplied by the user as direct context.
- Optional artifact persistence must use `ObjectStorage`.

## 10. Validation Strategy

- Require at least two funnel stages with counts or rates.
- Validate denominators, stage ordering, non-negative counts, finite rates, and period labels.
- Flag missing stages, inconsistent totals, small sample sizes, and attribution caveats.
- Ensure model-generated conclusions cite deterministic findings or user-provided evidence.
- Hard-flag requests to change campaigns or budgets automatically.

## 11. Quality Scoring Strategy

Agent 14 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Metric math correctness | 20 |
| Data quality and caveat handling | 15 |
| Bottleneck specificity | 20 |
| Evidence-backed hypotheses | 15 |
| Recommendation feasibility and prioritization | 15 |
| Experiment and measurement clarity | 10 |
| Executive clarity | 5 |

Pass if score >= 84 and no hard-fail flags.

## 12. Evaluation Strategy

Eval datasets should include clean funnels, missing stages, inconsistent denominators, small samples, clear bottlenecks, conflicting segment performance, prompt injection, and auto-activation requests.

CI gates:

- schema_valid = 100%
- metric_math_correctness >= 95%
- data_quality_detection >= 90%
- no_activation_behavior = 100%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 13. Error Handling Strategy

- Missing minimum funnel data returns `needs_human`.
- Invalid denominators return `needs_human` with correction guidance.
- Cost stop returns deterministic calculations plus `stopped_cost_ceiling`.
- Provider failure after deterministic calculations returns `error` or partial analysis depending on whether safe output exists.
- Activation/budget-change requests return hard-fail flags.

## 14. Telemetry Requirements

Emit through `Telemetry` only:

- request id, provider, model tier, terminal status
- spans for schema validation, deterministic calculations, comparison, anomaly detection, diagnosis, recommendation generation, scoring, and finalization
- token/cost by billable stage
- stage count, bottleneck count, data-quality warning count, quality score, and status
- no raw revenue, spend, account, lead, or customer data in logs

## 15. Cloud Agnostic Review

- Deterministic metric tools are local only.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`; telemetry through `Telemetry`.
- No cloud SDKs, analytics SDKs, CRM/MAP/ad-platform SDKs, warehouse SDKs, direct model SDKs, or `litellm` inside `agent/`.
- GCP, Bedrock, and Azure provider choices remain config-only.

## 16. Future Integration Considerations

- MarketingIQ Studio should render funnel tables, bottleneck rankings, and experiment backlog objects.
- Agent 12 KPI plans and Agent 13 journey plans should be accepted as optional structured context.
- Future live analytics connectors require provider-neutral read abstractions, least privilege, and data minimization.
- Future campaign optimization loops require HITL before changes are applied.
- Agent 14 can become the feedback source for improving Agents 10-13 after live performance data exists.

