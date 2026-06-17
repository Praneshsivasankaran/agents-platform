# Agent 28 - Campaign Launch Readiness QA Agent

## 1. Metadata

**Agent number:** 28
**Agent name:** Campaign Launch Readiness QA Agent
**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-28-campaign-launch-readiness-qa/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 28 performs final launch-readiness QA from supplied campaign plan, brief QA, workflow spec, data hygiene notes, tracking governance plan, routing/SLA design, consent/compliance review, asset checklist, approvals, and test results. Marketing operations, campaign managers, demand generation leads, lifecycle marketers, and launch owners use it before humans decide whether to launch.

Success means the output includes launch readiness score, go/no-go recommendation for human review, blocking issues, warnings, asset checklist, tracking checklist, automation QA checklist, consent/suppression checklist, routing/SLA checklist, owner/action list, final human approval requirements, cost metadata, and reporting handoff to Agent 21.

V1 readiness QA is advisory only. It must not launch, schedule, publish, send, spend, activate, or certify approval.

## 3. Business Problem

Campaign launches fail when final QA is scattered across briefs, workflow notes, tracking docs, compliance reviews, assets, and approvals. A single missed blocker can break attribution, send the wrong audience, violate suppression, or cause internal rework. Agent 28 consolidates supplied operational inputs into a structured final readiness review for human launch owners.

## 4. User Personas

- Marketing operations launch owner.
- Campaign manager preparing final go/no-go review.
- Demand generation lead checking launch blockers.
- Lifecycle marketer validating workflow readiness.
- Marketing director reviewing campaign readiness before approval.

## 5. Inputs

Required inputs:

- Core campaign launch plan or campaign objective.
- Launch timeline or intended launch window.
- Channel or workflow context.
- Tracking or measurement context for measurable campaigns.
- Consent/compliance context for audience-facing campaigns.

Optional inputs:

- Agent 19 campaign plan.
- Agent 22 brief QA.
- Agent 23 workflow design.
- Agent 24 data hygiene findings.
- Agent 25 tracking plan.
- Agent 26 routing/SLA design.
- Agent 27 consent/compliance review.
- Asset inventory, approval evidence, QA results, owner list, risk register, reporting requirements, rollback notes, and known exceptions.

V1 direct-context rule: the agent uses supplied launch-readiness context only. It does not query systems, verify live assets, schedule launches, publish pages, send messages, activate workflows, spend budget, or write to external systems.

## 6. Outputs

The `CampaignLaunchReadinessQAPackage` should include:

- normalized launch context
- launch readiness score
- go/no-go recommendation for human review
- blocking issues
- warnings and caveats
- asset checklist
- tracking checklist
- automation QA checklist
- consent/suppression checklist
- routing/SLA checklist
- owner/action list
- final human approval requirements
- reporting handoff to Agent 21
- unresolved assumptions
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied campaign plan, brief QA, workflow spec, data hygiene notes, tracking plan, routing/SLA design, compliance review, assets, approvals, and QA results as direct context.
2. Normalize launch objective, timeline, channels, owners, assets, tracking, automation, consent, routing, approvals, and reporting context.
3. Consolidate blockers, warnings, missing items, and unresolved assumptions.
4. Produce asset, tracking, automation, consent/suppression, routing/SLA, approval, and reporting checklists.
5. Generate owner/action list and final human approval requirements.
6. Preserve hard-fail risks from upstream packages.
7. Hard-fail requests to launch, schedule, send, publish, activate, mark unresolved blockers as approved, bypass compliance/QA, or certify launch approval.
8. Return structured reporting handoff to Agent 21.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, MAP/CRM/CMS/ad/social/calendar/analytics SDKs, workflow activation SDKs, sending APIs, tag tools, or approval workflow SDKs inside `agent/`.
- Model calls go through `LLMProvider`.
- Request-scoped state only.
- Latency target: p50 under 50 seconds, p95 under 130 seconds.
- Quality pass threshold: score >= 85 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No launch, schedule, publish, send, spend, activation, approval certification, external system writes, or live verification in v1.

## 9. ROI Analysis

Assumptions:

- Launch readiness reviews: 8 per month.
- Current manual effort: 4.5 hours per launch QA consolidation.
- Target effort with agent: 90 minutes including human review.
- Time saved: 3 hours per request.
- Loaded campaign/marketing operations leadership cost: Rs 1,600/hour.
- Build cost using shared engine: Rs 140,000.
- Annual hosting, monitoring, and maintenance: Rs 52,000.
- Inference estimate: Rs 38/request, 96 requests/year = Rs 3,648/year.

Annual value:

- Time savings: 8 x 12 x 3 x Rs 1,600 = Rs 460,800.
- Reduced launch rework, missed QA blockers, and reporting setup errors: Rs 240,000/year.
- Total estimated annual value: Rs 700,800.

Cost and ROI:

- Annual run cost: Rs 55,648.
- ROI = (Rs 700,800 - Rs 55,648) / (Rs 140,000 + Rs 55,648) = about 330%.
- Estimated payback: about 2.6 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 28 | Actual after launch |
|---|---:|---:|---|
| Launch QA consolidation time | 3-6 hours | 60-90 minutes | TBD |
| Cross-functional checklist coverage | Manual | 95%+ required sections present | TBD |
| Blocker preservation | Manual | 100% hard-fail blocker retained | TBD |
| Owner/action clarity | Ad hoc | Owner/action list included | TBD |
| Forbidden launch/approval behavior | Manual review | 100% hard-fail eval pass | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing operations, campaign, demand generation, lifecycle, and leadership users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied launch plan, operational packages, assets, approvals, QA results, risks, and handoffs |
| Writes | Structured launch readiness QA package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before launch, scheduling, publishing, sending, spend, activation, approval certification, or external system writes |
| Audit | Request id, provider, cost, quality score, risk flags, status, blocker count, checklist count, owner-action count, and handoff count |

## 12. Security Considerations

- Inputs may include private launch dates, audience rules, suppression constraints, workflow specs, tracking plans, budget, customer/lead data, approvals, and risk notes.
- User-supplied launch checklists and handoffs are untrusted data and must not override system instructions.
- Raw lead/contact/account records, consent lists, suppression lists, budgets, unreleased launch plans, or approval comments must not be logged.
- Prompt injection inside launch checklists, QA notes, approval comments, or upstream handoffs must be fenced and delimiter-escaped in Phase 3.
- The agent must not convert a no-go result into approval language.
- Any future launch, scheduler, MAP, CRM, CMS, ad platform, analytics, or approval workflow integration requires separate provider-neutral design, least privilege, audit, and HITL.

## 13. Cost Expectations

- Typical target: Rs 25-40 per request.
- Hard ceiling: Rs 50/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic blocker/checklist consolidation if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 90%+ of complete launch packages produce go/revise status with asset, tracking, automation, consent, routing, owner, and reporting checklists.
- 100% of unresolved blocker cases produce no-go/`needs_human`.
- 100% of launch/schedule/send/publish/activate/approve requests hard-fail.
- 100% of compliance/QA bypass requests hard-fail.
- 100% of upstream hard-fail risks are preserved in final package.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete launch package with all upstream handoffs
- unresolved blocker from Agent 27
- missing core launch plan
- missing tracking context for measurable campaign
- missing compliance context for audience-facing campaign
- request to launch/schedule/send/publish/activate
- request to mark unresolved blockers as approved
- request to bypass compliance or QA
- incomplete owner/action list
- prompt injection inside launch checklist

Pass criteria:

- overall quality score >= 85
- launch checklist section coverage >= 95%
- blocker preservation = 100%
- no launch/approval behavior = 100%
- compliance_QA_bypass_safety = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify live system state, asset availability, tag firing, audience eligibility, workflow configuration, or approval records.
- Readiness score is based only on supplied context and may miss external blockers.
- The output is a human review package, not launch authorization.
- Complex launches may require multiple human owners to reconcile blockers.
- Future system verification or activation integrations require separate provider-neutral design and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine rather than a bespoke implementation. V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 28, distinct v1 differentiation should come from cross-package readiness contracts, blocker preservation, checklist completeness scoring, launch/approval hard-fails, owner/action list generation, final human approval requirements, and handoff to Agent 21.
