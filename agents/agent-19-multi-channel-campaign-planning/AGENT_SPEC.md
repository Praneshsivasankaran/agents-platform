# Agent 19 - Multi-Channel Campaign Planning Agent

## 1. Metadata

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-19-multi-channel-campaign-planning/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 19 creates coordinated digital channel execution plans from supplied campaign recommendation, audience segments, budget, offer, content inventory, keywords, paid campaign guidance, landing page notes, timeline, and operational constraints. Marketing leaders, demand generation managers, campaign managers, and marketing operations teams use it when a chosen campaign direction needs a practical cross-channel plan for human execution.

Success means the output includes channel strategy, channel mix, campaign calendar, message sequencing, asset requirements, channel-specific briefs, dependencies, owner/handoff notes, measurement plan, quality score, risk flags, cost metadata, and handoff to Agent 21. V1 plans only; it does not launch, schedule, send, publish, or spend.

## 3. Business Problem

Campaign strategy often falls apart during execution because paid, content, email, landing page, nurture, and reporting workstreams are planned separately. Teams miss dependencies, duplicate messages, overload channels, or forget measurement needs. Agent 19 turns selected campaign context into a coordinated execution plan while preserving human control over every activation step.

## 4. User Personas

- Demand generation manager coordinating a launch.
- Campaign manager turning a recommended play into channel tasks.
- Marketing operations lead preparing handoffs for MAP/CRM and web teams.
- Content lead aligning campaign assets and messages.
- Founder/operator planning a practical multi-channel push.

## 5. Inputs

Required inputs:

- Campaign goal or chosen campaign direction.
- Target audience or segment.
- Offer or key message.
- Timeline or launch window.
- Channel list or channel constraints.

Optional inputs:

- Agent 08 ICP output.
- Agent 09 audience segments.
- Agent 10 lead generation blueprint.
- Agent 12 campaign recommendation.
- Agent 15 keyword research.
- Agent 16 ad copy themes.
- Agent 17 landing page notes.
- Agent 18 paid campaign recommendations.
- Budget, content inventory, owner list, approval process, consent/suppression constraints, regional constraints, and KPI plan.

V1 direct-context rule: all channel plans use supplied context only. The agent does not schedule posts, send emails, launch ads, write workflows, query platforms, or publish pages.

## 6. Outputs

The `MultiChannelCampaignPlanningPackage` should include:

- normalized campaign brief
- channel strategy and rationale
- channel mix
- campaign calendar
- message sequencing
- asset requirements and gaps
- channel-specific briefs
- dependency map
- owner and handoff notes
- measurement plan
- consent/suppression and risk notes
- downstream handoff to Agent 21
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept campaign, audience, channel, timeline, offer, and constraint inputs.
2. Normalize upstream handoffs into a planning context.
3. Recommend a channel mix based on supplied goals, audience, assets, and budget.
4. Create a campaign calendar and sequencing plan.
5. Define channel-specific briefs and asset requirements.
6. Identify dependencies, owners, missing assets, and approval needs.
7. Build a measurement plan suitable for Agent 21 reporting.
8. Flag consent, suppression, spam, deceptive-flow, protected-targeting, and operational risks.
9. Reject requests to launch, schedule, send, publish, spend, or bypass consent.
10. Return structured handoff notes for human execution and reporting.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, email/MAP/CRM/social/ad platform/CMS/calendar SDKs, or scheduler APIs inside `agent/`.
- Model calls go through `LLMProvider`.
- Request-scoped state only.
- Latency target: p50 under 45 seconds, p95 under 110 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No activation, scheduling, sending, publishing, workflow writes, budget spend, or external writes in v1.

## 9. ROI Analysis

Assumptions:

- Multi-channel campaign plans: 4 per month.
- Current manual effort: 7 hours per plan.
- Target effort with agent: 2 hours including review.
- Time saved: 5 hours per plan.
- Loaded campaign strategy/ops cost: Rs 1,500/hour.
- Build cost using shared engine: Rs 140,000.
- Annual hosting, monitoring, and maintenance: Rs 50,000.
- Inference estimate: Rs 38/request, 48 requests/year = Rs 1,824/year.

Annual value:

- Time savings: 4 x 12 x 5 x Rs 1,500 = Rs 360,000.
- Reduced coordination rework and missed dependencies: Rs 160,000/year.
- Total estimated annual value: Rs 520,000.

Cost and ROI:

- Annual run cost: Rs 51,824.
- ROI = (Rs 520,000 - Rs 51,824) / (Rs 140,000 + Rs 51,824) = about 244%.
- Estimated payback: about 3.6 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 19 | Actual after launch |
|---|---:|---:|---|
| Campaign planning time | 5-9 hours | 90-120 minutes | TBD |
| Dependency visibility | Manual | Dependency map included | TBD |
| Asset gap detection | Manual | 90%+ gaps flagged in evals | TBD |
| Channel brief completeness | Inconsistent | 90%+ required fields present | TBD |
| Activation boundary safety | Manual | 100% hard-fail eval pass | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved campaign, demand generation, marketing operations, content, and leadership users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied campaign context, content inventory, budget notes, constraints, and upstream handoffs |
| Writes | Structured campaign planning package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before any ad/email/social/CMS/MAP/CRM/calendar activation or budget spend |
| Audit | Request id, provider, cost, quality score, risk flags, status, channel count, and handoff count |

## 12. Security Considerations

- Inputs may include confidential launch plans, budget, revenue goals, audience strategy, customer segments, consent data, and regional constraints.
- User-supplied notes and handoffs are untrusted data and must not override instructions.
- The agent must not generate spammy, deceptive, non-consensual, or protected-targeting campaign flows.
- Raw PII, audience records, budget details, and suppression lists must not be logged.
- Prompt injection inside campaign briefs, content inventories, or upstream handoffs must be fenced and escaped in Phase 3.

## 13. Cost Expectations

- Typical target: Rs 25-40 per request.
- Hard ceiling: Rs 50/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with safe partial planning sections if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 90%+ of complete eval cases produce channel strategy, calendar, sequencing, assets, dependencies, and measurement plan.
- 90%+ of pass outputs include at least one owner/handoff note per active channel.
- 100% of activation/scheduling/sending/publishing/spend requests hard-fail.
- 100% of consent bypass requests hard-fail.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete campaign recommendation plus audience and budget
- missing timeline
- missing content inventory
- conflicting channel constraints
- request to launch/schedule/send/publish
- request to bypass suppression or consent
- spammy/deceptive flow request
- prompt injection inside upstream handoff
- protected targeting attempt

Pass criteria:

- overall quality score >= 84
- required planning sections present >= 90%
- no activation behavior = 100%
- consent/suppression safety = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot schedule or activate work; humans must execute in external systems.
- Plans are limited by supplied inventory, budget, owner, and timeline context.
- Calendar recommendations are planning dates, not scheduled posts or sends.
- Future live MAP/CRM/ad/social/CMS integrations require separate design, least privilege, audit, and HITL.
- Overly broad campaign goals may require human strategy clarification.

## 17. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine rather than a bespoke implementation. V1 may use a shared Digital Marketing engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 19, distinct v1 differentiation should come from channel-plan contracts, calendar/dependency validation, consent/suppression risk rules, activation hard fails, and eval cases around coordinated campaign planning.
