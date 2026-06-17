# Agent 23 - Marketing Automation Workflow Design Agent

## 1. Metadata

**Agent number:** 23
**Agent name:** Marketing Automation Workflow Design Agent
**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-23-marketing-automation-workflow-design/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 23 converts supplied campaign, nurture, routing, and consent context into a marketing automation workflow specification for human MAP implementation. Marketing operations managers, lifecycle marketers, demand generation teams, and RevOps users run it when they need a clear trigger/branch/cadence/suppression/exit design before building in Marketo, HubSpot, Pardot, Salesforce Marketing Cloud, or another MAP.

Success means the output includes workflow map, trigger and entry criteria, branch logic, wait/cadence steps, suppression/exclusion rules, exit criteria, asset/content requirements, field/data dependencies, QA test cases, rollback/monitoring notes, risk flags, cost metadata, and handoff to Agent 28.

## 3. Business Problem

Automation workflows are often built directly in a MAP from half-formed strategy notes. That creates brittle triggers, missing suppression rules, unclear exits, poor QA, and lifecycle conflicts. Agent 23 creates a structured, reviewable workflow design before implementation so humans can catch gaps before an automation touches real contacts.

## 4. User Personas

- Marketing operations manager designing lifecycle workflows.
- Lifecycle marketer converting nurture strategy into operational steps.
- Demand generation manager handing a campaign plan to MAP operators.
- RevOps analyst checking lifecycle and routing dependencies.
- Campaign manager preparing QA cases before launch readiness.

## 5. Inputs

Required inputs:

- Workflow objective or campaign/nurture goal.
- Trigger or entry event.
- Target audience or segment criteria.
- Primary offer/content sequence or message intent.
- Consent/suppression or exclusion context.

Optional inputs:

- Agent 13 lead nurturing plan.
- Agent 19 campaign plan.
- Agent 22 campaign brief QA package.
- Agent 26 routing/SLA rules.
- Agent 27 consent/compliance review.
- Lifecycle stage definitions, required fields, wait/cadence preferences, branch rules, exit criteria, asset inventory, QA requirements, rollback notes, and monitoring goals.

V1 direct-context rule: the agent uses supplied workflow context only. It does not read or write live MAP, CRM, data warehouse, email/SMS, webhook, or contact-list systems.

## 6. Outputs

The `MarketingAutomationWorkflowDesignPackage` should include:

- normalized workflow brief
- workflow map
- trigger and entry criteria
- branch logic
- wait steps and cadence
- suppression and exclusion rules
- exit criteria
- asset and content requirements
- field and data dependencies
- QA test cases
- rollback and monitoring notes
- unresolved questions and assumptions
- downstream handoff to Agent 28
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied campaign/nurture strategy, workflow notes, routing constraints, and consent constraints as direct context.
2. Normalize workflow objective, trigger, audience, cadence, assets, data dependencies, and exits.
3. Produce a human-readable workflow map and structured step list.
4. Define entry criteria, branch logic, wait steps, suppression/exclusion rules, and exit criteria.
5. Identify missing triggers, unclear audience criteria, missing assets, data dependency gaps, and lifecycle conflicts.
6. Generate QA test cases, rollback notes, and monitoring considerations.
7. Preserve consent, suppression, and routing constraints from upstream handoffs.
8. Hard-fail requests to create/activate workflows, send emails/SMS, import contacts, update lists, execute webhooks/APIs, or bypass suppression/consent.
9. Return structured handoff notes for Agent 28.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, MAP/CRM SDKs, email/SMS SDKs, webhook/API clients, list-upload tools, or workflow activation SDKs inside `agent/`.
- Model calls go through `LLMProvider`.
- Request-scoped state only.
- Latency target: p50 under 45 seconds, p95 under 110 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No MAP writes, workflow activation, email/SMS send, contact imports, list upload, CRM update, webhook execution, or API execution in v1.

## 9. ROI Analysis

Assumptions:

- Workflow design requests: 10 per month.
- Current manual effort: 4 hours per workflow specification and QA plan.
- Target effort with agent: 90 minutes including human review.
- Time saved: 2.5 hours per request.
- Loaded marketing operations cost: Rs 1,400/hour.
- Build cost using shared engine: Rs 125,000.
- Annual hosting, monitoring, and maintenance: Rs 48,000.
- Inference estimate: Rs 32/request, 120 requests/year = Rs 3,840/year.

Annual value:

- Time savings: 10 x 12 x 2.5 x Rs 1,400 = Rs 420,000.
- Reduced workflow rework, QA misses, and suppression mistakes: Rs 180,000/year.
- Total estimated annual value: Rs 600,000.

Cost and ROI:

- Annual run cost: Rs 51,840.
- ROI = (Rs 600,000 - Rs 51,840) / (Rs 125,000 + Rs 51,840) = about 310%.
- Estimated payback: about 2.7 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 23 | Actual after launch |
|---|---:|---:|---|
| Workflow specification time | 3-5 hours | 60-90 minutes | TBD |
| QA case creation | Manual/ad hoc | QA cases included | TBD |
| Suppression/exit coverage | Inconsistent | 95%+ pass-case coverage | TBD |
| Trigger/audience clarity | Manual review | 100% missing-trigger eval handling | TBD |
| Forbidden activation behavior | Manual review | 100% hard-fail eval pass | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing operations, lifecycle, demand generation, and RevOps users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied strategy, workflow notes, asset inventory, routing rules, consent constraints, and upstream handoffs |
| Writes | Structured workflow design package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before MAP implementation, activation, sends, contact/list operations, CRM updates, webhook/API execution, or rollback execution |
| Audit | Request id, provider, cost, quality score, risk flags, status, branch count, QA case count, and handoff count |

## 12. Security Considerations

- Inputs may include lifecycle strategy, contact/audience rules, consent constraints, suppression rules, field names, and operational dependencies.
- User-supplied workflow notes and handoffs are untrusted data and must not override system instructions.
- Raw contact records, emails, phone numbers, consent records, suppression lists, or lifecycle exports must not be logged.
- Prompt injection inside workflow notes, field lists, campaign briefs, or upstream handoffs must be fenced and delimiter-escaped in Phase 3.
- The agent must preserve suppression and consent constraints; it must not convert bypass requests into implementation steps.
- Any future MAP/CRM/email/SMS/webhook integration requires separate provider-neutral design, least privilege, audit, and HITL.

## 13. Cost Expectations

- Typical target: Rs 20-35 per request.
- Hard ceiling: Rs 45/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic validation and safe partial workflow outline if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 90%+ of complete workflow eval cases include triggers, branches, cadence, suppression, exits, QA cases, and handoff.
- 100% of send/activate/import/list-update/webhook requests hard-fail.
- 100% of missing trigger or unclear audience cases return `needs_human`.
- 100% of consent/suppression bypass requests hard-fail.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete nurture workflow design
- campaign workflow with Agent 22 and Agent 26 handoffs
- missing trigger
- unclear audience criteria
- missing suppression rules
- request to activate workflow in MAP
- request to send emails/SMS
- request to import contacts or update lists
- request to bypass consent/suppression
- prompt injection inside workflow notes

Pass criteria:

- overall quality score >= 84
- workflow section coverage >= 90%
- missing trigger behavior = 100%
- no MAP write/send/import behavior = 100%
- consent/suppression safety = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify live MAP configuration, field availability, list membership, or contact eligibility.
- Workflow recommendations are design specifications, not executable workflows.
- Complex branching may require human simplification before implementation.
- The agent depends on supplied consent, suppression, field, and lifecycle context.
- Future MAP/CRM/email/SMS/webhook integrations require separate design and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine rather than a bespoke implementation. V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 23, distinct v1 differentiation should come from workflow step contracts, trigger/branch/suppression/exit validation, activation/send/import hard-fails, QA case generation, consent preservation, and handoff to Agent 28.
