# Agent 14 - Conversion Analysis Agent

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-14-conversion-analysis/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## v1 Architecture Note — Shared Demand Generation Engine

v1 of Agents 08-14 runs on a shared Demand Generation engine
(`packages/demand_generation`): one common LangGraph workflow, cost gate (Rs.50
ceiling), telemetry, risk detection, and quality-scoring spine, reused so the
family stays consistent and cloud-agnostic. Each agent remains distinct through
its own **profile** (required fields, forbidden actions, protected/leaky terms,
recommended outputs, handoff targets, quality dimensions, thresholds, and cost
ceiling), **config overlays** (`base`/`gcp`/`bedrock`/`azure`), **schemas**,
**prompts**, **scoring dimensions**, **risk rules**, and **evals**. The
deterministic domain logic unique to this agent today is deterministic funnel conversion math and denominator-consistency / sample-size checks.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Use Case

Agent 14 analyzes user-provided funnel, campaign, segment, and conversion performance data to identify conversion bottlenecks and recommend optimization actions. It produces funnel diagnostics, conversion-rate calculations, segment/source comparisons, root-cause hypotheses, prioritized experiments, KPI impact estimates, data-quality warnings, and executive-ready insights.

V1 analyzes supplied data only. It does not connect to analytics systems, modify campaigns, run experiments, or optimize live traffic.

## 2. Business Problem

Demand generation teams often have campaign and funnel data but struggle to turn it into clear action. Bottlenecks can be hidden across landing page conversion, form completion, MQL quality, sales acceptance, opportunity creation, and nurture progression. Agent 14 standardizes conversion analysis so teams can prioritize improvements before spending more budget.

## 3. User Personas

- Demand generation manager reviewing campaign performance.
- Marketing analyst preparing funnel diagnostics.
- Growth marketer prioritizing optimization tests.
- Marketing operations leader investigating data quality or routing gaps.
- Executive marketing leader reviewing conversion and pipeline contribution.

## 4. Inputs

- Campaign, funnel, segment, source, or channel performance data supplied by the user.
- Counts and rates such as visitors, clicks, form fills, leads, MQLs, SQLs, opportunities, pipeline, won revenue, and drop-offs.
- Time period, campaign name, audience segment, source/channel, and region.
- Agent 10/12 KPI plan or Agent 13 nurture plan, if available.
- Benchmarks, qualitative notes, known anomalies, and business constraints.
- Data-quality notes and attribution caveats.

## 5. Outputs

- Conversion analysis package with executive summary.
- Funnel table with calculated conversion rates and drop-offs.
- Bottleneck ranking with severity and confidence.
- Segment/source/channel comparison insights.
- Root-cause hypotheses and evidence.
- Prioritized optimization recommendations.
- Experiment backlog with expected impact and measurement plan.
- Data-quality warnings, attribution caveats, risk flags, quality score, status, and cost metadata.

## 6. Functional Requirements

1. Accept structured funnel metrics and pasted performance summaries as direct input.
2. Normalize metric names, periods, stages, and segments.
3. Calculate conversion rates, drop-offs, and basic comparisons deterministically.
4. Identify bottlenecks and data anomalies.
5. Generate root-cause hypotheses tied to supplied evidence.
6. Recommend prioritized experiments or operational fixes.
7. Flag missing data, inconsistent denominators, attribution caveats, and unsupported conclusions.
8. Return a structured conversion analysis package with quality score and cost usage.

## 7. Non Functional Requirements

- Cloud/provider selection must be config-driven.
- Agent logic must not import cloud SDKs, analytics SDKs, CRM/MAP SDKs, ad-platform SDKs, direct model SDKs, or `litellm`.
- Model calls go through `LLMProvider`; deterministic metric calculations should avoid model calls where possible.
- No live data reads, campaign writes, experiment activation, or budget changes in v1.
- Typical latency target: p50 under 45 seconds and p95 under 120 seconds for normal summary inputs.
- Quality threshold: score >= 84 and no hard-fail flags.
- Output must be explainable and audit-friendly.

## 8. ROI Analysis

Assumptions:

- Conversion analysis reports: 4 per month.
- Current manual effort: 12 hours per report.
- Target effort with agent: 4 hours including review.
- Time saved: 8 hours per report.
- Loaded analytics/demand generation cost: Rs 1,500/hour.
- Build cost using existing platform patterns: Rs 140,000.
- Annual hosting, monitoring, and maintenance: Rs 78,000.
- Inference estimate: Rs 45/request, 48 requests/year = Rs 2,160/year.

Annual value:

- Time savings: 4 x 12 x 8 x Rs 1,500 = Rs 576,000.
- Conversion improvement and prioritization value: Rs 500,000/year.
- Total estimated annual value: Rs 1,076,000.

Cost and ROI:

- Annual run cost: Rs 80,160.
- ROI = (Rs 1,076,000 - Rs 80,160) / (Rs 140,000 + Rs 80,160) = about 452%.
- Estimated payback: about 1.7 months.

## 9. Efficiency Targets

| Metric | Baseline today | Target with Agent 14 | Actual after launch |
|---|---:|---:|---|
| Funnel analysis prep | 8-16 hours | 2-4 hours | TBD |
| Bottleneck identification | Manual | 90%+ correct in evals | TBD |
| Data-quality issue detection | Inconsistent | 90%+ flagged in evals | TBD |
| Experiment backlog creation | 2-4 hours | 30-60 minutes | TBD |
| Executive summary preparation | 1-2 hours | 15-30 minutes | TBD |

## 10. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved demand generation, analytics, marketing operations, and marketing leadership users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-submitted funnel metrics, campaign summaries, benchmarks, and direct-context notes |
| Writes | Structured conversion analysis package, quality/cost metrics, redacted logs, optional provider-neutral artifact reference |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before future analytics queries, campaign changes, test activation, or budget updates |
| Audit | Request id, metric-stage counts, quality score, risk flags, provider, cost, and status through `Telemetry` |

## 11. Security Considerations

- Inputs may include pipeline, revenue, campaign spend, attribution, account, and lead data.
- Raw performance data and revenue numbers must not be logged.
- Source notes are untrusted content.
- The agent must not overstate causality from correlation-only data.
- The agent must not recommend changes that require external activation without human review.
- Future live analytics or CRM integrations require separate access design and least-privilege scopes.

## 12. Cost Expectations

- Typical target: under Rs 25-45 per analysis.
- Hard ceiling: Rs 50/request in v1 config.
- Metric calculations should be deterministic and local; model calls should focus on diagnosis and explanation.
- If the ceiling would be exceeded, return deterministic calculations and partial insights with `stopped_cost_ceiling`.

## 13. Success Metrics

- 90%+ of complete-input eval cases calculate rates and drop-offs correctly.
- 85%+ of complete-input eval cases identify the expected primary bottleneck.
- 90%+ of data-quality issue cases are flagged.
- 100% of eval runs avoid live-system writes or activation.
- 100% of eval runs stay under cost ceiling.

## 14. Evaluation Criteria

Eval cases should include:

- Complete funnel with clear landing-page bottleneck.
- Strong lead volume but poor MQL-to-SQL conversion.
- Segment-level conversion difference.
- Inconsistent denominators or missing stages.
- Small sample size and unreliable rates.
- Prompt injection inside pasted performance notes.
- Request to automatically change campaign budget.

Pass criteria:

- Overall score >= 84.
- Metric math correctness >= 95%.
- Data-quality issue detection >= 90%.
- No activation behavior = 100%.
- Schema validity and cost adherence = 100%.

## 15. Risks and Limitations

- V1 cannot verify source-system accuracy or attribution logic.
- Recommendations may be wrong if supplied data is incomplete or poorly defined.
- Small sample sizes can produce misleading rates.
- Correlation does not prove causality; the agent must present hypotheses, not certainty.
- It does not run experiments, change campaigns, or query live analytics in v1.

