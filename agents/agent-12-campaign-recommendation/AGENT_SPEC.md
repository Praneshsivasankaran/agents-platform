# Agent 12 - Campaign Recommendation Agent

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-12-campaign-recommendation/`
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
deterministic domain logic unique to this agent today is ranked campaign-option planning with budget and dependency rationale.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Use Case

Agent 12 recommends demand generation campaign plays from supplied ICPs, audience segments, business goals, budget, channel constraints, offer inventory, and past performance summaries. It returns ranked campaign recommendations with rationale, target audience, channel mix, budget split, content/asset needs, KPI plan, experiment design, dependencies, risks, and downstream handoff notes.

V1 recommends and plans campaigns. It does not spend budget, publish content, upload audiences, send messages, or optimize live campaigns automatically.

## 2. Business Problem

Demand generation teams frequently choose campaigns based on preference, urgency, or incomplete channel performance data. This leads to poor channel-fit, unclear KPIs, weak offers, and budget waste. Agent 12 creates a repeatable recommendation process that compares campaign options against the audience, goal, constraints, and evidence before execution starts.

## 3. User Personas

- Demand generation director planning quarterly campaign mix.
- Growth marketer choosing a campaign play for a segment.
- Marketing operations manager checking feasibility and dependencies.
- Product marketing manager aligning message, offer, and audience.
- Marketing leader reviewing budget and expected outcomes.

## 4. Inputs

- Agent 08 ICP package and Agent 09 segmentation package.
- Optional Agent 10 lead generation blueprint.
- Business objective, funnel stage, target pipeline/revenue goal, and priority audience.
- Budget range, timeline, regions, channel availability, and operational constraints.
- Existing offers, assets, content inventory, and sales plays.
- Past campaign summaries supplied as direct context.
- Brand, compliance, consent, and approval requirements.

## 5. Outputs

- Ranked campaign recommendations.
- Recommended primary campaign play and backup options.
- Audience/segment mapping and message angle.
- Channel mix and budget allocation guidance.
- Asset/content requirements.
- KPI plan, leading indicators, success thresholds, and experiment design.
- Operational dependency checklist.
- Risk flags, missing inputs, quality score, terminal status, and cost metadata.
- Handoff notes for lead generation, nurture, and conversion analysis.

## 6. Functional Requirements

1. Accept ICP, segment, goal, budget, channel, and performance context as direct input.
2. Normalize objective, constraints, and available assets.
3. Generate multiple campaign options.
4. Score and rank options against goal fit, audience fit, channel fit, feasibility, cost/risk, and expected learning value.
5. Produce a concrete recommended plan with KPIs and experiment design.
6. Flag weak assumptions, missing dependencies, unrealistic budgets, and compliance constraints.
7. Return structured handoffs for Agents 10, 13, and 14.

## 7. Non Functional Requirements

- Cloud selection must be config-driven.
- Agent logic must not import cloud SDKs, ad-platform SDKs, CRM/MAP SDKs, analytics SDKs, direct model SDKs, or `litellm`.
- Model calls go through `LLMProvider`; telemetry goes through `Telemetry`.
- No external writes, live optimization, autonomous web research, or activation in v1.
- Typical latency target: p50 under 40 seconds and p95 under 100 seconds.
- Quality threshold: score >= 82 and no hard-fail flags.
- Output must support human campaign planning in future MarketingIQ Studio.

## 8. ROI Analysis

Assumptions:

- Campaign recommendation/planning cycles: 5 per month.
- Current manual effort: 10 hours per cycle.
- Target effort with agent: 2 hours including review.
- Time saved: 8 hours per cycle.
- Loaded demand generation strategy cost: Rs 1,400/hour.
- Build cost using existing platform patterns: Rs 140,000.
- Annual hosting, monitoring, and maintenance: Rs 66,000.
- Inference estimate: Rs 35/request, 60 requests/year = Rs 2,100/year.

Annual value:

- Time savings: 5 x 12 x 8 x Rs 1,400 = Rs 672,000.
- Budget efficiency and avoided rework: Rs 400,000/year.
- Total estimated annual value: Rs 1,072,000.

Cost and ROI:

- Annual run cost: Rs 68,100.
- ROI = (Rs 1,072,000 - Rs 68,100) / (Rs 140,000 + Rs 68,100) = about 482%.
- Estimated payback: about 1.7 months.

## 9. Efficiency Targets

| Metric | Baseline today | Target with Agent 12 | Actual after launch |
|---|---:|---:|---|
| Campaign option analysis | 6-12 hours | 60-150 minutes | TBD |
| KPI and experiment planning | 2-4 hours | 30-60 minutes | TBD |
| Dependency visibility | Inconsistent | 90%+ required dependencies surfaced | TBD |
| Campaign recommendation consistency | Variable | Standard scoring/rationale produced | TBD |
| Budget-fit review | Manual | Budget risks flagged in evals | TBD |

## 10. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved demand generation, marketing leadership, growth, and marketing operations users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-submitted ICP, segments, goals, budgets, assets, constraints, and direct-context performance summaries |
| Writes | Structured recommendation package, quality/cost metrics, redacted logs, optional provider-neutral artifact reference |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before future budget spend, audience upload, publishing, campaign activation, or system writes |
| Audit | Request id, selected recommendation, score, risk flags, provider, cost, and status through `Telemetry` |

## 11. Security Considerations

- Inputs can include budget, pipeline goals, target markets, campaign performance, and confidential launch strategy.
- The agent must not reveal or log raw budget/performance details.
- Consent and suppression constraints must remain hard constraints.
- Source notes are untrusted content.
- No live ad, email, CRM, MAP, or analytics system writes in v1.
- Recommendations that imply regulated or sensitive targeting must be flagged for human review.

## 12. Cost Expectations

- Typical target: under Rs 20-35 per recommendation package.
- Hard ceiling: Rs 45/request in v1 config.
- Cost tracked per stage and emitted through `Telemetry`.
- If cost would exceed the ceiling, return ranked partial recommendations with `stopped_cost_ceiling`.

## 13. Success Metrics

- 85%+ of complete-input eval cases produce at least three ranked campaign options.
- 90%+ of pass outputs include audience, channel, KPI, budget, experiment, and dependency sections.
- 90%+ of unrealistic budget or missing dependency cases are flagged.
- 100% of eval runs avoid external activation.
- 100% of eval runs stay under cost ceiling.

## 14. Evaluation Criteria

Eval cases should include:

- Enterprise pipeline-generation goal with ICP and segments.
- Low-budget campaign request.
- Conflicting goal, channel, and timeline constraints.
- Prior performance summary showing channel underperformance.
- Compliance-constrained regional campaign.
- Prompt injection inside performance notes.
- Request to activate campaign spend automatically.

Pass criteria:

- Overall score >= 82.
- Campaign option ranking rationale >= 85.
- No external activation behavior = 100%.
- Schema validity and cost adherence = 100%.

## 15. Risks and Limitations

- Recommendation quality depends on supplied performance context.
- V1 cannot validate real-time inventory, CPM/CPC, email deliverability, or list size.
- Budget allocation guidance is advisory, not financial authorization.
- Campaign options may be too generic if ICP, offer, or constraints are weak.
- Human approval is required before spend or activation.

