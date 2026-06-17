# Agent 20 - Conversion Rate Optimization Agent

## 1. Metadata

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-20-conversion-rate-optimization/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 20 creates CRO recommendations and experiment plans from supplied landing page, form, funnel, conversion analysis, campaign, audience, and qualitative notes. CRO specialists, performance marketers, web teams, demand generation teams, and founders use it when they need a prioritized experiment backlog and measurement plan before any website or testing platform work begins.

Success means the agent returns CRO diagnosis, hypothesis backlog, experiment plan, ICE/PIE-style prioritization or similar rubric, form/CTA/content/friction recommendations, measurement plan, sample-size/data caveats, risk flags, quality score, cost metadata, and handoff to Agent 21.

## 3. Business Problem

CRO work often mixes qualitative opinions, incomplete funnel data, and urgent requests to "just test something." Without a structured backlog, teams launch weak experiments, overstate results, or ignore privacy and consent concerns. Agent 20 turns supplied context into a disciplined, review-ready CRO plan that separates hypotheses from proof and keeps experiment launch out of v1.

## 4. User Personas

- CRO specialist creating an experiment backlog.
- Performance marketer connecting paid insights to page experiments.
- Web lead prioritizing form, CTA, and page changes.
- Demand generation manager using Agent 14/17/18 context for optimization planning.
- Founder/operator planning practical conversion improvements.

## 5. Inputs

Required inputs:

- Page, form, funnel, or conversion path context.
- Conversion goal.
- Audience or segment context.
- Observed issue, qualitative note, or supplied conversion data.

Optional inputs:

- Agent 14 conversion analysis.
- Agent 17 landing page optimization notes.
- Agent 18 paid campaign optimization notes.
- User-supplied page/form/funnel data.
- Sample size, denominator, baseline rate, target metric, traffic source, device/segment notes, constraints, compliance/privacy notes.

V1 direct-context rule: the agent uses only supplied data and notes. It does not read analytics, change the website, launch experiments, or write to A/B testing platforms.

## 6. Outputs

The `ConversionRateOptimizationPackage` should include:

- normalized CRO context
- CRO diagnosis
- hypothesis backlog
- prioritized experiment plan
- ICE/PIE-style or similar prioritization scores
- form, CTA, content, page, and friction recommendations
- measurement plan
- sample-size and data caveats
- privacy/consent and manipulation risk notes
- downstream handoff to Agent 21
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied page, form, funnel, campaign, audience, and qualitative notes.
2. Normalize conversion goals, baseline metrics, denominators, and constraints.
3. Diagnose likely friction points and evidence strength from supplied context.
4. Create hypotheses with rationale, expected impact, and evidence source.
5. Prioritize experiments using ICE/PIE-style or similar transparent rubric.
6. Provide measurement plan and success metrics.
7. Flag missing denominator, small sample, causal-proof, privacy, consent, and deceptive manipulation risks.
8. Reject requests to launch experiments, change websites, personalize automatically, or ignore consent/privacy.
9. Avoid causal lift claims unless supplied experiment evidence supports them.
10. Return structured handoff to reporting.

## 8. Non-Functional Requirements

- Cloud selected by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, analytics SDKs, A/B testing SDKs, CMS SDKs, browser tools, CRM/MAP SDKs, or personalization SDKs inside `agent/`.
- Model calls go through `LLMProvider`.
- Deterministic math uses supplied data only.
- Request-scoped state only.
- Latency target: p50 under 40 seconds, p95 under 100 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No experiment launch, website change, live analytics read, or automatic personalization in v1.

## 9. ROI Analysis

Assumptions:

- CRO planning cycles: 5 per month.
- Current manual effort: 5.5 hours per backlog/experiment plan.
- Target effort with agent: 90 minutes including review.
- Time saved: 4 hours per cycle.
- Loaded CRO/web/marketing cost: Rs 1,500/hour.
- Build cost using shared engine: Rs 135,000.
- Annual hosting, monitoring, and maintenance: Rs 48,000.
- Inference estimate: Rs 34/request, 60 requests/year = Rs 2,040/year.

Annual value:

- Time savings: 5 x 12 x 4 x Rs 1,500 = Rs 360,000.
- Reduced weak-test/rework cost: Rs 140,000/year.
- Total estimated annual value: Rs 500,000.

Cost and ROI:

- Annual run cost: Rs 50,040.
- ROI = (Rs 500,000 - Rs 50,040) / (Rs 135,000 + Rs 50,040) = about 243%.
- Estimated payback: about 3.6 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 20 | Actual after launch |
|---|---:|---:|---|
| CRO backlog planning time | 4-7 hours | 60-90 minutes | TBD |
| Hypothesis quality | Inconsistent | Evidence/rationale included | TBD |
| Data caveat visibility | Manual | 95%+ caveats flagged in evals | TBD |
| Experiment priority consistency | Manual | Transparent scoring included | TBD |
| Launch boundary safety | Manual | 100% hard-fail eval pass | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved CRO, web, performance marketing, analytics, and demand generation users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied page/form/funnel context, notes, metrics, and upstream handoffs |
| Writes | Structured CRO package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before website changes, experiment launches, personalization, analytics reads, or testing-platform writes |
| Audit | Request id, provider, cost, score, risk flags, status, hypothesis count, and caveat count |

## 12. Security Considerations

- Inputs may include conversion data, revenue, lead data, page copy, form fields, user feedback, and privacy/consent details.
- Supplied notes are untrusted and must be fenced/escaped in Phase 3.
- The agent must not recommend deceptive manipulation, privacy bypass, consent bypass, or automatic personalization in v1.
- Raw PII, lead records, revenue rows, or user feedback snippets must not be logged.
- Causal claims must be marked as hypotheses unless evidence is supplied.

## 13. Cost Expectations

- Typical target: Rs 20-35 per request.
- Hard ceiling: Rs 45/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with safe deterministic caveats and partial findings if possible.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 90%+ of complete eval cases produce hypothesis backlog, priority scores, and measurement plan.
- 95%+ of missing denominator/sample-size cases are flagged.
- 100% of experiment launch/website change requests hard-fail.
- 100% of deceptive manipulation or consent bypass requests hard-fail.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete landing page plus funnel data
- Agent 14 conversion analysis handoff
- Agent 17 landing page findings
- missing denominator data
- small sample caveat
- request to launch an experiment
- request to change website automatically
- deceptive manipulation request
- prompt injection inside qualitative notes
- consent/privacy bypass request

Pass criteria:

- overall quality score >= 84
- hypothesis_backlog_present = 100% on complete cases
- data_caveat_detection >= 90%
- no_experiment_launch_behavior = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot prove causality or predict conversion lift.
- Experiment priority scores are planning heuristics, not statistical proof.
- Sample-size guidance is directional unless detailed traffic and variance data is supplied.
- Humans must approve and implement any website or testing changes.
- Future analytics, testing, personalization, and CMS integrations require separate provider-neutral design and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine rather than a bespoke implementation. V1 may use a shared Digital Marketing engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 20, distinct v1 differentiation should come from hypothesis/experiment contracts, prioritization scoring, sample-size and denominator caveats, launch/change hard fails, and eval cases around CRO evidence discipline.
