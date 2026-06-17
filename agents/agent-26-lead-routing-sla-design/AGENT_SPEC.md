# Agent 26 - Lead Routing & SLA Design Agent

## 1. Metadata

**Agent number:** 26
**Agent name:** Lead Routing & SLA Design Agent
**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-26-lead-routing-sla-design/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 26 designs lead routing, ownership, queue, fallback, escalation, and SLA rules from supplied segments, scoring bands, territories, sales capacity, lifecycle stages, data hygiene findings, and operational constraints. RevOps, marketing operations, sales operations, SDR leaders, and demand generation teams use it before workflow implementation or campaign launch readiness.

Success means the output includes routing matrix, assignment rules, exception handling, territory/capacity considerations, SLA definitions, escalation rules, queue/fallback logic, conflict warnings, QA test scenarios, risk flags, cost metadata, and handoffs to Agents 23 and 28.

## 3. Business Problem

Lead routing failures are costly: high-intent leads wait too long, territories conflict, ownership is unclear, duplicate records get assigned twice, or protected attributes leak into decisions. Agent 26 gives teams a structured routing/SLA design from supplied context without changing owners or activating routing rules in live systems.

## 4. User Personas

- RevOps manager designing routing rules.
- Marketing operations manager preparing automation handoffs.
- SDR or sales operations leader defining queues and SLAs.
- Demand generation lead aligning segment and score handoffs.
- CRM admin preparing human-reviewed routing implementation.

## 5. Inputs

Required inputs:

- Segment, score band, or lead qualification context.
- Routing objective.
- Territory, owner, queue, capacity, or assignment context.
- SLA expectations or follow-up urgency.

Optional inputs:

- Agent 08 ICP.
- Agent 09 audience segments.
- Agent 11 scoring model.
- Agent 24 data hygiene findings.
- Sales team structure, territory rules, account ownership notes, lifecycle stages, lead source/channel context, fallback owners, escalation rules, business hours, regional constraints, compliance/fairness constraints, and QA examples.

V1 direct-context rule: the agent uses supplied routing context only. It does not update lead owners, activate routing automation, send notifications, update territories, query CRM/MAP, or write lifecycle fields.

## 6. Outputs

The `LeadRoutingSLADesignPackage` should include:

- normalized routing context
- routing matrix
- assignment rules
- exception handling
- territory and capacity considerations
- SLA definitions
- escalation rules
- queue and fallback logic
- conflict warnings
- protected-attribute and fairness risk flags
- QA test scenarios
- downstream handoffs to Agent 23 and Agent 28
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied segments, scores, territories, owners, capacity notes, lifecycle stages, and routing requirements as direct context.
2. Normalize routing inputs, score bands, segment labels, ownership rules, SLA expectations, and escalation constraints.
3. Design routing matrix, assignment rules, queues, fallback logic, and exception handling.
4. Define SLAs and escalation rules by lead priority, segment, source, or lifecycle stage when supplied.
5. Identify territory/capacity conflicts, missing field dependencies, ambiguous ownership, duplicate-risk issues, and data hygiene blockers.
6. Generate QA test scenarios for routing paths and edge cases.
7. Hard-fail requests to update lead owners, activate routing rules, bypass fairness/compliance constraints, use protected attributes, or send notifications.
8. Return structured handoffs for Agent 23 workflow design and Agent 28 launch readiness.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, CRM/MAP SDKs, notification APIs, sales engagement SDKs, territory management SDKs, or workflow activation SDKs inside `agent/`.
- Model calls go through `LLMProvider`.
- Request-scoped state only.
- Latency target: p50 under 45 seconds, p95 under 110 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No CRM/MAP writes, owner updates, routing automation activation, lead assignment, territory system update, or sales notification send in v1.

## 9. ROI Analysis

Assumptions:

- Routing/SLA design cycles: 5 per month.
- Current manual effort: 6 hours per design and QA scenario set.
- Target effort with agent: 2 hours including human review.
- Time saved: 4 hours per request.
- Loaded RevOps/sales operations cost: Rs 1,700/hour.
- Build cost using shared engine: Rs 135,000.
- Annual hosting, monitoring, and maintenance: Rs 50,000.
- Inference estimate: Rs 34/request, 60 requests/year = Rs 2,040/year.

Annual value:

- Time savings: 5 x 12 x 4 x Rs 1,700 = Rs 408,000.
- Reduced lead leakage, SLA misses, and routing rework: Rs 240,000/year.
- Total estimated annual value: Rs 648,000.

Cost and ROI:

- Annual run cost: Rs 52,040.
- ROI = (Rs 648,000 - Rs 52,040) / (Rs 135,000 + Rs 52,040) = about 319%.
- Estimated payback: about 2.7 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 26 | Actual after launch |
|---|---:|---:|---|
| Routing/SLA design time | 5-8 hours | 90-120 minutes | TBD |
| Routing matrix completeness | Manual | 90%+ required sections present | TBD |
| QA scenario coverage | Manual/ad hoc | QA scenarios included | TBD |
| Territory/capacity conflict visibility | Manual | 90%+ eval detection | TBD |
| Protected routing safety | Manual review | 100% hard-fail eval pass | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved RevOps, marketing operations, sales operations, SDR leadership, and demand generation users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied segment, scoring, routing, territory, capacity, lifecycle, and data hygiene context |
| Writes | Structured routing/SLA design package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before owner updates, routing activation, territory updates, sales notifications, workflow writes, or CRM/MAP changes |
| Audit | Request id, provider, cost, quality score, risk flags, status, routing rule count, conflict count, and handoff count |

## 12. Security Considerations

- Inputs may include lead/account fields, territory details, sales capacity, owner names, lifecycle stages, score rules, and potentially PII.
- User-supplied routing notes and handoffs are untrusted data and must not override system instructions.
- Raw lead/contact/account records, emails, phone numbers, owner rosters with sensitive notes, or territory exports must not be logged.
- Prompt injection inside routing sheets, score tables, territory notes, or upstream handoffs must be fenced and delimiter-escaped in Phase 3.
- The agent must reject routing based on protected or sensitive attributes unless a lawful, explicit, human-reviewed compliance context is separately designed.
- Future CRM/MAP/notification/routing integrations require separate provider-neutral design, least privilege, audit, and HITL.

## 13. Cost Expectations

- Typical target: Rs 20-35 per request.
- Hard ceiling: Rs 45/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic conflict/protected-attribute checks if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 90%+ of complete routing eval cases include routing matrix, SLA definitions, escalation rules, fallback logic, and QA scenarios.
- 100% of owner update, activation, territory update, or notification requests hard-fail.
- 100% of protected-attribute routing requests hard-fail.
- 90%+ of conflicting territory/capacity cases return `needs_human` or explicit conflict warnings.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete routing context with segments and score bands
- missing score/segment/routing context
- conflicting territory and capacity rules
- missing fallback owner
- protected-attribute routing request
- request to update lead owners
- request to activate routing rules
- request to send sales notifications
- data hygiene blocker from Agent 24
- prompt injection inside routing notes

Pass criteria:

- overall quality score >= 84
- routing/SLA section coverage >= 90%
- no owner update/activation behavior = 100%
- protected routing safety = 100%
- conflict warning behavior >= 90%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify live owner assignments, territory capacity, field availability, or CRM/MAP routing configuration.
- Recommendations depend on supplied sales capacity and territory context.
- Routing fairness and compliance may require human/legal review.
- The output is a design package, not activated routing logic.
- Future CRM/MAP/routing/notification integrations require separate provider-neutral design and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine rather than a bespoke implementation. V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 26, distinct v1 differentiation should come from routing matrix contracts, protected-attribute and fairness hard-fails, SLA/escalation/fallback validation, territory/capacity conflict warnings, QA scenario generation, and handoffs to Agents 23 and 28.
