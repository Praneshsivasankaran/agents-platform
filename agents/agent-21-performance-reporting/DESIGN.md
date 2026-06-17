# Agent 21 - Performance Reporting Agent Design

## 1. Metadata

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-21-performance-reporting/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 21 creates stakeholder-ready digital marketing performance reports from supplied metrics and context. It must calculate simple rates/deltas deterministically, surface data-quality caveats, and produce truthful narrative summaries without querying live systems or distributing reports.

## 3. Agent Boundaries

In scope:

- Normalize supplied metrics and KPI definitions.
- Calculate simple rates, deltas, totals, and scorecard fields where denominators are present.
- Generate executive summaries, channel tables, caveats, recommendations, and stakeholder variants.
- Flag misrepresentation, live-query, send/distribution, denominator, and attribution risks.

Out of scope:

- Live analytics/API reads, dashboard publishing, CRM/MAP/ad-platform/warehouse queries, automated report distribution, or hiding/misrepresenting performance.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_reporting_context
3. validate_metrics_kpis_and_period
4. calculate_rates_deltas_and_totals
5. detect_data_quality_and_attribution_caveats
6. build_kpi_scorecard_and_channel_table
7. generate_reporting_narrative
8. create_recommendations_and_next_steps
9. generate_stakeholder_variants
10. detect_live_query_send_and_misrepresentation_risks
11. score_reporting_package
12. assemble_performance_reporting_package
13. finalize_response
```

Deterministic stages include metric validation, rate/delta math, denominator checks, live-query/send/misrepresentation detection, and score/status mapping. LLM-assisted stages create narrative summaries and recommendations grounded in deterministic findings.

## 5. State Model

Request-scoped state should contain:

- normalized reporting context
- metric inventory and KPI definitions
- deterministic calculations
- data-quality and attribution caveats
- KPI scorecard and channel table
- narrative summary
- recommendations and next actions
- stakeholder variants
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain analytics clients, dashboard clients, CRM/MAP/ad platform clients, warehouse clients, sending clients, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- reporting period, campaign objective, stakeholder audience, KPI plan
- supplied metrics and channel summaries
- budget/spend/revenue/pipeline/conversion data if supplied
- prior period or benchmark values if supplied
- Agent 12, 14, 18, and 20 handoffs
- business context, caveats, known anomalies, recommendations to include

## 7. Outputs

Primary output concepts:

- `PerformanceReportingPackage`
- `ExecutiveSummary`
- `KPIScorecard`
- `ChannelPerformanceRow`
- `DeterministicCalculation`
- `DataQualityCaveat`
- `AttributionCaveat`
- `BudgetSpendSummary`
- `Recommendation`
- `NextStepAction`
- `StakeholderReportVariant`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `PerformanceReportingRequest`
- `MetricInput`
- `KPIDefinition`
- `CalculatedMetric`
- `ChannelPerformanceTable`
- `ReportNarrative`
- `DataQualityCaveat`
- `StakeholderVariant`
- `PerformanceReportingQualityReport`
- `PerformanceReportingPackage`

Shared status, risk, evidence, cost, and handoff contracts should be reused.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_reporting_inputs` | request | missing fields and blockers | None | Local only |
| `calculate_rates_and_deltas` | supplied metrics | CTR, CVR, CPA, ROAS, deltas where possible | None | Local only |
| `detect_denominator_and_total_issues` | metric rows | data-quality warnings | None | Local only |
| `detect_misrepresentation_requests` | request/narrative | hard-fail risk flags | None | Local only |
| `detect_live_query_or_send_requests` | request text | live-action hard-fail flags | None | Local only |
| `score_reporting_package` | report and risks | quality report | None | Local only |

No analytics, dashboard, ad platform, CRM, MAP, warehouse, email, messaging, or publishing tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent performance memory in v1.
- Prior reports or period data can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require reporting period, objective/KPI context, and at least one supplied metric or channel summary.
- Validate denominators before calculating rates.
- Mark undefined or inconsistent metrics clearly.
- Hard-flag requests to hide bad results, misrepresent performance, query live systems, or send reports.
- Ensure narrative claims cite supplied data, deterministic calculations, or caveats.
- Avoid causal claims unless the user supplies experiment evidence.

## 12. Quality Scoring Strategy

Agent 21 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Metric and KPI correctness | 20 |
| Data-quality and attribution caveat handling | 15 |
| Executive summary clarity | 15 |
| Channel performance table usefulness | 15 |
| Recommendation and next-step actionability | 15 |
| Stakeholder variant fit | 10 |
| Truthfulness and misrepresentation safety | 10 |

Pass if score >= 84 and no hard-fail risk.

## 13. Evaluation Strategy

Eval datasets should cover complete multi-channel reports, missing denominator, inconsistent totals, negative performance, request to hide bad results, live analytics query, auto-send request, prompt injection, and small sample caveats.

CI gates:

- schema_valid = 100%
- calculation_correctness >= 95%
- denominator_warning_accuracy >= 90%
- no_misrepresentation_behavior = 100%
- no_live_query_or_send_behavior = 100%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 14. Error Handling Strategy

- Missing reporting context returns `needs_human`.
- Invalid denominators return caveats and may return `needs_human`.
- Misrepresentation, live-query, or auto-send requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with deterministic scorecard if available.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 15. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for validation, calculations, caveat detection, scorecard creation, narrative generation, scoring, finalization
- token/cost by stage
- KPI count, calculation count, caveat count, channel count, stakeholder variant count, quality score, risk counts
- no raw revenue rows, account data, lead records, PII, customer names, or full report notes in logs

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
- No cloud SDKs, analytics SDKs, dashboard SDKs, ad platform SDKs, CRM/MAP SDKs, warehouse SDKs, email/sending SDKs, direct model SDKs, or `litellm` inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents; Bedrock and Azure remain config/stub compatible.
- Shared `packages/digital_marketing` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render scorecards, channel tables, caveats, recommendations, and stakeholder variants. Studio can later support connector-backed data refresh or report distribution only after separate provider-neutral read/write designs and human approval gates.

## 19. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine with an Agent 21 profile. The profile should define reporting sections, deterministic metric calculations, misrepresentation hard-fails, stakeholder variant rules, quality dimensions, and eval cases. Future versions may add provider-neutral analytics connectors, but live reads and automated distribution remain out of v1.
