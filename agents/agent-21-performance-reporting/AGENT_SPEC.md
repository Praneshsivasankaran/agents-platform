# Agent 21 - Performance Reporting Agent

## 1. Metadata

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-21-performance-reporting/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 21 creates stakeholder-ready digital marketing performance reports from supplied campaign metrics, channel data summaries, KPI plans, conversion analysis, paid campaign notes, CRO experiment notes, and business context. Marketing leaders, campaign managers, paid media teams, analysts, and founders use it when they need a clear report package for review, not an automatically sent dashboard.

Success means the output includes executive summary, KPI scorecard, channel performance table, campaign highlights, risks/issues, conversion/funnel summary, budget/spend summary if supplied, recommendations, next-step action list, data-quality caveats, stakeholder-specific variants, quality score, risk flags, cost metadata, and handoff to future optimization cycles.

## 3. Business Problem

Performance reporting is repetitive and high stakes. Teams need to calculate rates, summarize results, explain caveats, show underperformance honestly, and tailor narrative for executives or operators. Manual reports often hide weak data quality, overstate causality, or take too long. Agent 21 creates a structured reporting package from supplied data while refusing to misrepresent performance.

## 4. User Personas

- Marketing leader preparing an executive update.
- Campaign manager summarizing multi-channel results.
- Paid media manager reporting spend and optimization actions.
- Marketing analyst converting raw summaries into a narrative.
- Founder/operator preparing investor or leadership updates.

## 5. Inputs

Required inputs:

- Campaign or reporting objective.
- Reporting period.
- Supplied campaign metrics or channel summaries.
- KPI definitions or business goals.

Optional inputs:

- Agent 12 campaign goals or KPI plan.
- Agent 14 conversion analysis.
- Agent 18 paid campaign optimization notes.
- Agent 20 CRO experiment plans.
- Spend, budget, revenue, leads, opportunities, conversions, impressions, clicks, CTR, CPC, CVR, CPA, ROAS, channel notes, segment notes, stakeholder audience, and prior period data.

V1 direct-context rule: the agent uses supplied metrics only. It does not query analytics, dashboards, CRM, MAP, ad platforms, data warehouses, or live APIs.

## 6. Outputs

The `PerformanceReportingPackage` should include:

- normalized reporting context
- executive summary
- KPI scorecard
- channel performance table
- deterministic calculations and formula notes
- campaign highlights
- risks and issues
- conversion/funnel summary
- budget/spend summary if supplied
- recommendations and next-step action list
- data-quality caveats
- stakeholder-specific report variants
- assumptions and missing-data warnings
- handoff to future optimization cycles
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied metrics, KPI definitions, period, and business context.
2. Normalize channel, campaign, metric, and stakeholder context.
3. Calculate simple rates, deltas, and totals deterministically where denominators are supplied.
4. Flag missing, inconsistent, stale, or undefined data.
5. Generate executive summary and stakeholder-specific narrative variants.
6. Explain performance without overstating causality.
7. Include negative results and risks honestly.
8. Reject requests to query live analytics, send reports, hide bad results, or misrepresent performance.
9. Return recommendations tied to supplied metrics and caveats.
10. Produce structured handoff notes for future optimization cycles.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, analytics SDKs, dashboard SDKs, CRM/MAP SDKs, ad platform SDKs, warehouse SDKs, or email/sending SDKs inside `agent/`.
- Model calls go through `LLMProvider`.
- Deterministic calculations use supplied data only.
- Request-scoped state only.
- Latency target: p50 under 40 seconds, p95 under 100 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No live analytics/API reads, dashboard publishing, CRM/MAP/ad-platform queries, or automated distribution in v1.

## 9. ROI Analysis

Assumptions:

- Performance report cycles: 6 per month.
- Current manual effort: 4 hours per report.
- Target effort with agent: 75 minutes including review.
- Time saved: 2.75 hours per report.
- Loaded marketing analytics/leadership cost: Rs 1,500/hour.
- Build cost using shared engine: Rs 130,000.
- Annual hosting, monitoring, and maintenance: Rs 48,000.
- Inference estimate: Rs 30/request, 72 requests/year = Rs 2,160/year.

Annual value:

- Time savings: 6 x 12 x 2.75 x Rs 1,500 = Rs 297,000.
- Reduced reporting rework and executive clarification cycles: Rs 125,000/year.
- Total estimated annual value: Rs 422,000.

Cost and ROI:

- Annual run cost: Rs 50,160.
- ROI = (Rs 422,000 - Rs 50,160) / (Rs 130,000 + Rs 50,160) = about 206%.
- Estimated payback: about 4.2 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 21 | Actual after launch |
|---|---:|---:|---|
| Report drafting time | 3-5 hours | 45-75 minutes | TBD |
| KPI calculation consistency | Manual | 95%+ deterministic assertions pass | TBD |
| Data-quality caveat visibility | Manual | 95%+ caveats flagged in evals | TBD |
| Misrepresentation prevention | Manual review | 100% hard-fail eval pass | TBD |
| Stakeholder variant readiness | Ad hoc | Structured variants included | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing leadership, campaign, paid media, analytics, and operations users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied metrics, summaries, KPI plans, notes, and upstream handoffs |
| Writes | Structured reporting package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before live data integrations, dashboard publishing, or report distribution |
| Audit | Request id, provider, cost, score, risk flags, status, KPI count, calculation count, and caveat count |

## 12. Security Considerations

- Inputs may include confidential spend, revenue, pipeline, customer, account, lead, and regional data.
- Supplied reports and notes are untrusted and must not override system instructions.
- Raw PII, account records, revenue rows, or customer details must not be logged.
- The agent must not hide negative results, fabricate improvement, or misrepresent attribution.
- Prompt injection inside report notes, pasted metric tables, or stakeholder instructions must be fenced and escaped in Phase 3.
- Automated report sending or dashboard publishing is out of scope.

## 13. Cost Expectations

- Typical target: Rs 20-35 per request.
- Hard ceiling: Rs 45/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic calculations and safe partial summary if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 95%+ of deterministic KPI/rate calculations match expected formulas in evals.
- 95%+ of missing/inconsistent denominator cases are flagged.
- 100% of hide-negative-results and misrepresentation requests hard-fail.
- 100% of live analytics/query/send requests hard-fail or require future HITL integration.
- 100% schema-valid outputs and cost ceiling adherence.
- 90%+ of complete reports include executive summary, KPI scorecard, channel table, caveats, and next actions.

## 15. Evaluation Criteria

Eval cases should include:

- complete multi-channel report summary
- paid campaign report with spend/conversions
- missing denominator for CVR/CPA
- inconsistent totals
- negative performance that must not be hidden
- request to misrepresent or hide bad results
- request to query live analytics
- request to send reports automatically
- prompt injection inside report notes
- small sample or attribution caveat

Pass criteria:

- overall quality score >= 84
- deterministic_calculation_correctness >= 95%
- no_misrepresentation_behavior = 100%
- no_live_query_or_send_behavior = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify live source-system data; the user must supply accurate metrics.
- Attribution and causality must remain caveated unless experiment evidence is supplied.
- Reports are drafts for human review and distribution outside the agent.
- Missing denominators limit rate calculations.
- Future analytics, dashboard, CRM/MAP, warehouse, and distribution integrations require separate provider-neutral design, least privilege, audit, and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine rather than a bespoke implementation. V1 may use a shared Digital Marketing engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 21, distinct v1 differentiation should come from reporting contracts, deterministic KPI/rate calculators, misrepresentation hard fails, data-quality caveats, stakeholder variant scoring, and eval cases around truthful reporting.
