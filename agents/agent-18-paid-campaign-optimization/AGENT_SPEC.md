# Agent 18 - Paid Campaign Optimization Agent

## 1. Metadata

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-18-paid-campaign-optimization/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 18 analyzes supplied paid campaign structure and performance summaries to recommend optimization actions for budgets, bids, targeting, keywords, creatives, placements, and landing pages. Paid media managers and demand generation teams use it when they have exported or summarized campaign data and need review-ready recommendations before a human changes anything in an ad platform.

Success means the agent returns optimization findings tied to supplied metrics, campaign/ad group/ad set issues, advisory budget reallocation suggestions, keyword/creative/audience recommendations, wasted-spend and pacing flags, experiment plan, confidence levels, risk flags, quality score, cost metadata, and handoffs to Agents 19, 20, and 21.

## 3. Business Problem

Paid campaign optimization requires repeated review of spend, pacing, CTR, CPC, CVR, CPA, ROAS, creative performance, targeting, keyword waste, and landing page alignment. Teams often make changes from partial evidence or delay reviews because the analysis is time-consuming. Agent 18 structures the review while keeping changes advisory and preventing unauthorized budget or platform actions.

## 4. User Personas

- Paid media manager reviewing weekly performance exports.
- Growth marketer preparing optimization recommendations for approval.
- Demand generation manager coordinating paid findings with channel planning.
- Marketing analyst summarizing spend and conversion issues.
- Founder/operator auditing small campaign accounts manually.

## 5. Inputs

Required inputs:

- Campaign objective or goal.
- Supplied campaign structure or performance summary.
- Channel/platform context.
- At least one supplied metric or qualitative performance note.

Optional inputs:

- Agent 12 campaign recommendation.
- Agent 15 keyword research.
- Agent 16 ad copy output.
- Agent 17 landing page notes.
- Budget, spend, pacing, CTR, CPC, CVR, CPA, ROAS, impression share, conversion data, placement data, search term summaries, audience notes, and constraints.

V1 direct-context rule: the agent uses only supplied summaries/exports. It does not access ad platform APIs, analytics APIs, CRM, MAP, or live dashboards.

## 6. Outputs

The `PaidCampaignOptimizationPackage` should include:

- normalized campaign performance summary
- optimization findings tied to supplied data
- campaign/ad group/ad set issue list
- advisory budget reallocation suggestions
- bid, keyword, audience, placement, creative, and landing page recommendations
- wasted-spend and pacing risk flags
- confidence levels and evidence notes
- experiment plan
- missing-data and denominator warnings
- downstream handoffs to Agents 19, 20, and 21
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied campaign structure and performance summaries.
2. Normalize channel, campaign, ad group/ad set, keyword, creative, and landing page context.
3. Calculate or verify simple supplied rates only when denominators are present.
4. Identify optimization findings tied to supplied metrics.
5. Flag wasted spend, pacing risks, low-confidence recommendations, missing data, and inconsistent denominators.
6. Provide advisory budget reallocation suggestions without authorizing budget changes.
7. Recommend keyword, creative, audience, placement, and landing page optimization actions.
8. Reject requests to change budgets, pause/launch campaigns, upload audiences, edit ads, or optimize without supplied data.
9. Return experiment plan and downstream handoffs.
10. Preserve human review before operational use.

## 8. Non-Functional Requirements

- Cloud selected by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, ad platform SDKs, analytics SDKs, CRM/MAP SDKs, or warehouse SDKs inside `agent/`.
- Model calls go through `LLMProvider`.
- Deterministic math is local and uses only supplied data.
- Latency target: p50 under 40 seconds, p95 under 100 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No live optimization, budget changes, ad edits, campaign pause/launch, audience upload, or external writes.

## 9. ROI Analysis

Assumptions:

- Campaign optimization reviews: 6 per month.
- Current manual effort: 4.5 hours per review.
- Target effort with agent: 90 minutes including human review.
- Time saved: 3 hours per review.
- Loaded paid media cost: Rs 1,500/hour.
- Build cost using shared engine: Rs 130,000.
- Annual hosting, monitoring, and maintenance: Rs 48,000.
- Inference estimate: Rs 32/request, 72 requests/year = Rs 2,304/year.

Annual value:

- Time savings: 6 x 12 x 3 x Rs 1,500 = Rs 324,000.
- Reduced wasted-spend review rework: Rs 150,000/year.
- Total estimated annual value: Rs 474,000.

Cost and ROI:

- Annual run cost: Rs 50,304.
- ROI = (Rs 474,000 - Rs 50,304) / (Rs 130,000 + Rs 50,304) = about 235%.
- Estimated payback: about 3.7 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 18 | Actual after launch |
|---|---:|---:|---|
| Weekly optimization review | 3-6 hours | 60-90 minutes | TBD |
| Metric-linked findings | Manual | 90%+ cite supplied data | TBD |
| Missing denominator warnings | Manual | 95%+ flagged in evals | TBD |
| Forbidden action blocking | Manual | 100% in hard-fail evals | TBD |
| Reporting handoff readiness | Ad hoc | Structured handoff available | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved paid media, demand generation, marketing analytics, and campaign users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied campaign summaries, exports, metrics, notes, and upstream handoffs |
| Writes | Structured optimization package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before any ad platform read/write, budget change, campaign edit, or audience upload |
| Audit | Request id, provider, cost, quality score, risk flags, status, and metric source labels |

## 12. Security Considerations

- Inputs may contain confidential budget, spend, revenue, conversion, audience, account, and campaign strategy data.
- Supplied exports and reports are untrusted data and must not override system instructions.
- Raw spend, revenue, lead, account, or customer data must not be logged.
- Recommendations must not use protected or sensitive targeting.
- Prompt injection inside pasted reports, search terms, campaign notes, or spreadsheets must be fenced and escaped in Phase 3.
- The agent must not imply it changed, paused, launched, or edited campaigns.

## 13. Cost Expectations

- Typical target: Rs 20-35 per request.
- Hard ceiling: Rs 45/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with safe deterministic data-quality findings where possible.
- Cost is tracked and emitted per stage.

## 14. Success Metrics

- 90%+ of complete eval cases produce optimization findings tied to supplied metrics.
- 95%+ of missing/inconsistent denominator cases are flagged.
- 100% of budget change, pause, launch, audience upload, and auto-edit requests hard-fail.
- 100% of unsupported metric claims are flagged.
- 100% schema-valid outputs.
- 100% cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete paid search performance export summary
- paid social creative performance summary
- missing conversion denominator
- inconsistent spend/conversion data
- optimization request with no supplied data
- request to change budgets or pause campaigns
- request to upload audience
- prompt injection inside report notes
- protected targeting attempt

Pass criteria:

- overall quality score >= 84
- metric_tie_rate >= 90% on complete cases
- no_live_action_behavior = 100%
- denominator_warning_accuracy >= 90%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify live platform state or attribution beyond supplied data.
- Budget recommendations are advisory and must be approved by a human.
- Weak or incomplete data reduces confidence and should route to `needs_human`.
- ROAS, CPA, and CVR claims require supplied denominators and definitions.
- Future ad platform and analytics integrations require separate provider-neutral read/write design, scopes, audit, and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine rather than a bespoke implementation. V1 may use a shared Digital Marketing engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 18, distinct v1 differentiation should come from metric-linked optimization outputs, paid-action hard fails, denominator/data-quality checks, advisory budget language, and eval cases around supplied performance data.
