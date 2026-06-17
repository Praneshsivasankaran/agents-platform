# Agent 22 - Campaign Intake & Brief QA Agent

## 1. Metadata

**Agent number:** 22
**Agent name:** Campaign Intake & Brief QA Agent
**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-22-campaign-intake-brief-qa/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 22 checks whether a campaign intake request or campaign brief is complete, clear, operationally feasible, and ready to move into execution planning. Marketing coordinators, campaign managers, demand generation leads, content leads, and marketing operations teams use it when a campaign request arrives from sales, leadership, product, or another marketing agent.

Success means the output gives a brief completeness score, missing information warnings, unclear requirement flags, dependency and owner gaps, asset and approval gaps, risk flags, clarifying questions, a ready/revise/reject recommendation, and structured handoffs to Agents 23, 25, and 28.

## 3. Business Problem

Campaign work often starts from incomplete requests: unclear objective, vague audience, missing launch date, no owner, missing approvals, weak offer, absent tracking expectations, or no asset inventory. Those gaps cause rework downstream in automation, tracking, creative, and launch QA. Agent 22 creates a consistent front-door QA step so teams can fix missing context before execution planning begins.

## 4. User Personas

- Marketing coordinator triaging campaign requests.
- Campaign manager preparing an execution brief.
- Demand generation lead checking whether a recommended play is operationally ready.
- Marketing operations manager validating owners, dates, approvals, and dependencies.
- Content or digital marketing lead handing off copy, page, or channel work.

## 5. Inputs

Required inputs:

- Campaign objective.
- Target audience or segment.
- Offer or key message.
- Requested channel or campaign type.
- Timeline, launch window, or requested due date.

Optional inputs:

- Campaign requester, owner, stakeholder, approval path, budget, region, product, funnel stage, content inventory, asset list, landing page notes, tracking requirements, consent/suppression constraints, success metrics, risk notes, and source labels.
- Upstream handoffs from Agent 12 campaign recommendation, Agent 19 multi-channel campaign plan, Agent 15 keyword strategy, Agent 16 ad copy themes, or Agent 17 landing page notes.

V1 direct-context rule: the agent uses only supplied briefs, notes, and structured handoffs. It does not query project tools, calendars, CRM, MAP, CMS, ad platforms, analytics, or document stores.

## 6. Outputs

The `CampaignIntakeBriefQAPackage` should include:

- normalized campaign brief
- brief completeness score
- missing information warnings
- unclear requirement flags
- dependency gaps
- owner and approval gaps
- asset gaps
- tracking and measurement gaps
- consent/suppression and operational risk flags
- clarifying questions
- readiness recommendation
- downstream handoffs to Agents 23, 25, and 28
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept campaign briefs, intake forms, pasted notes, and upstream handoffs as direct context.
2. Normalize campaign objective, audience, offer, timeline, channel, owner, and approval context.
3. Check required fields and score brief completeness.
4. Identify unclear requirements, contradictions, dependencies, owners, approvals, missing assets, and measurement gaps.
5. Flag consent, suppression, protected-targeting, launch, scheduling, publishing, and auto-approval risks.
6. Generate concise clarifying questions grouped by blocker, warning, or nice-to-have.
7. Recommend `approve`, `revise`, or `reject` for operational planning readiness.
8. Hard-fail requests to create project tasks, approve campaigns automatically, launch/schedule/send/publish, or bypass approvals.
9. Return structured handoffs for Agents 23, 25, and 28.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, project-management SDKs, calendar SDKs, MAP/CRM/CMS/ad platform SDKs, analytics SDKs, or scheduling APIs inside `agent/`.
- Model calls go through `LLMProvider`; optional persistence goes through `ObjectStorage`; secrets go through `SecretStore`; telemetry goes through `Telemetry`.
- Request-scoped state only.
- Latency target: p50 under 35 seconds, p95 under 90 seconds.
- Quality pass threshold: score >= 82 and no hard-fail risk.
- Output must be schema-valid and suitable for future MarketingIQ Studio rendering.
- No project/task creation, workflow system writes, campaign launch, scheduling, CMS/MAP/CRM/ad platform writes, or approval certification in v1.

## 9. ROI Analysis

Assumptions:

- Campaign intake reviews: 20 per month.
- Current manual effort: 75 minutes per intake review and clarification cycle.
- Target effort with agent: 25 minutes including human review.
- Time saved: 50 minutes per request.
- Loaded campaign/marketing operations cost: Rs 1,200/hour.
- Build cost using shared engine: Rs 105,000.
- Annual hosting, monitoring, and maintenance: Rs 42,000.
- Inference estimate: Rs 20/request, 240 requests/year = Rs 4,800/year.

Annual value:

- Time savings: 20 x 12 x 0.83 x Rs 1,200 = Rs 239,040.
- Reduced downstream rework and missed-dependency cost: Rs 120,000/year.
- Total estimated annual value: Rs 359,040.

Cost and ROI:

- Annual run cost: Rs 46,800.
- ROI = (Rs 359,040 - Rs 46,800) / (Rs 105,000 + Rs 46,800) = about 206%.
- Estimated payback: about 4.0 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 22 | Actual after launch |
|---|---:|---:|---|
| Intake review time | 60-90 minutes | 20-30 minutes | TBD |
| Required brief coverage | Inconsistent | 95%+ required fields checked | TBD |
| Clarification turnaround | 1-3 cycles | 1 structured question set | TBD |
| Owner/dependency visibility | Manual | 90%+ gaps flagged in evals | TBD |
| Forbidden launch/approval behavior | Manual review | 100% hard-fail eval pass | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing coordinators, campaign managers, demand generation, content, and marketing operations users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied campaign briefs, notes, asset summaries, constraints, and upstream handoffs |
| Writes | Structured QA package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before project/task creation, campaign approval, scheduling, publishing, sending, or launch |
| Audit | Request id, provider, cost, quality score, risk flags, status, missing-field count, and handoff count |

## 12. Security Considerations

- Inputs may include confidential campaign plans, budgets, launch timing, target accounts, audience strategy, approvals, and sensitive customer or lead context.
- User-supplied briefs and handoffs are untrusted data and must not override system instructions.
- Raw PII, account lists, suppression details, budgets, and private launch notes must not be logged.
- Prompt injection inside campaign briefs, pasted notes, asset lists, or upstream handoffs must be fenced and delimiter-escaped in Phase 3.
- The agent must not approve campaigns, bypass required approvals, or create tasks in external systems.
- Any future project-management, calendar, MAP, CRM, CMS, or launch integration requires separate provider-neutral design, least privilege, audit, and HITL.

## 13. Cost Expectations

- Typical target: Rs 15-25 per request.
- Hard ceiling: Rs 35/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic missing-field and risk checks if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 95%+ of complete brief eval cases produce `pass` and `quality_status=approve`.
- 100% of missing objective or missing audience cases return `needs_human`.
- 100% of auto-approval, task-creation, launch, send, schedule, or publish requests hard-fail.
- 90%+ of pass outputs include missing-field, owner, dependency, approval, and tracking sections.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete campaign brief with owners and timeline
- missing objective
- missing target audience
- unclear launch window and no owner
- missing asset inventory
- request to create project tasks directly
- request to approve campaign automatically
- request to launch, schedule, send, or publish
- prompt injection inside campaign notes

Pass criteria:

- overall quality score >= 82
- required brief QA sections present >= 90%
- missing objective/audience handling = 100%
- no forbidden live-action behavior = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify whether owners, assets, approvals, or dates are true in external systems.
- The agent depends on supplied context; it should label assumptions clearly.
- Brief approval is advisory only and requires human sign-off.
- Missing or contradictory stakeholder inputs may require manual reconciliation.
- Future workflow/project-system integrations require separate provider-neutral designs and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine rather than a bespoke implementation. V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 22, distinct v1 differentiation should come from brief completeness contracts, missing-field and owner/dependency validation, approval/launch hard-fails, clarifying-question generation, readiness scoring, and handoffs to Agents 23, 25, and 28.
