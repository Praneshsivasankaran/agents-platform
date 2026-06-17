# Agent 27 - Consent & Compliance Review Agent

## 1. Metadata

**Agent number:** 27
**Agent name:** Consent & Compliance Review Agent
**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-27-consent-compliance-review/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 27 reviews supplied campaign, segmentation, automation, tracking, audience, consent, suppression, data-use, regional, and brand-policy context for operational compliance risks. Marketing operations, legal/compliance coordinators, lifecycle marketers, demand generation teams, and campaign managers use it before automation or launch readiness review.

Success means the output includes consent/compliance risk assessment, suppression requirements, regional/data-residency warnings, protected/sensitive targeting flags, required approvals/HITL notes, legal-review recommendation where needed, mitigation checklist, risk flags, cost metadata, and handoff to Agent 28.

Agent 27 is not legal advice, not a lawyer, and not a legal/compliance certification system.

## 3. Business Problem

Marketing campaigns can easily violate consent, suppression, regional, privacy, brand, or protected-targeting constraints when teams rush from plan to execution. Manual reviews are inconsistent and often happen too late. Agent 27 creates a structured risk review from supplied context so humans can address blockers before launch.

## 4. User Personas

- Marketing operations manager checking consent and suppression readiness.
- Campaign manager preparing launch readiness materials.
- Lifecycle marketer reviewing nurture or automation plans.
- Demand generation lead checking audience and targeting risks.
- Legal/compliance coordinator triaging whether formal review is needed.

## 5. Inputs

Required inputs:

- Campaign, audience, automation, tracking, or data-use context.
- Region or market context if applicable.
- Consent, suppression, privacy, compliance, or approval notes.
- Intended channels or messaging context.

Optional inputs:

- Agent 09 segmentation.
- Agent 13 nurture plan.
- Agent 16 ad copy.
- Agent 19 campaign plan.
- Agent 22 brief QA.
- Agent 23 workflow design.
- Consent basis notes, suppression list requirements, privacy policy notes, data residency constraints, sensitive category notes, brand/legal guidelines, prior approval requirements, and known unresolved risks.

V1 direct-context rule: the agent uses supplied compliance context only. It does not read live consent databases, edit suppression lists, upload audiences, certify legal compliance, approve launch, or write to external systems.

## 6. Outputs

The `ConsentComplianceReviewPackage` should include:

- normalized compliance context
- consent and suppression risk assessment
- regional and data-residency warnings
- protected/sensitive targeting flags
- privacy and data-use risk notes
- brand/policy risk notes
- required approvals and HITL notes
- legal-review recommendation where needed
- mitigation checklist
- unresolved blocker list
- downstream handoff to Agent 28
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied campaign, segmentation, automation, tracking, consent, suppression, and compliance notes as direct context.
2. Normalize channel, audience, region, data-use, consent, suppression, and approval context.
3. Identify consent, suppression, privacy, regional, data-residency, protected-targeting, sensitive-category, and brand/policy risks.
4. Produce a mitigation checklist and required approvals/HITL notes.
5. State clearly that the output is not legal advice and not legal certification.
6. Recommend formal legal/compliance review where risks are high, ambiguous, regional, or unresolved.
7. Hard-fail requests to bypass consent/suppression, target protected/sensitive groups, certify legal compliance, approve launch despite high-risk issues, or ignore regional/data-residency constraints.
8. Return structured handoff notes for Agent 28.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, consent database SDKs, CRM/MAP SDKs, legal research APIs, suppression list tools, audience upload APIs, or approval workflow SDKs inside `agent/`.
- Model calls go through `LLMProvider`.
- Request-scoped state only.
- Latency target: p50 under 45 seconds, p95 under 120 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No legal advice, legal certification, policy certification, live consent database reads, suppression edits, audience uploads, activation approvals, or external system writes in v1.

## 9. ROI Analysis

Assumptions:

- Consent/compliance triage reviews: 8 per month.
- Current manual effort: 3 hours per campaign risk review and mitigation checklist.
- Target effort with agent: 75 minutes including human review.
- Time saved: 1.75 hours per request.
- Loaded marketing operations/compliance coordination cost: Rs 1,800/hour.
- Build cost using shared engine: Rs 130,000.
- Annual hosting, monitoring, and maintenance: Rs 50,000.
- Inference estimate: Rs 34/request, 96 requests/year = Rs 3,264/year.

Annual value:

- Time savings: 8 x 12 x 1.75 x Rs 1,800 = Rs 302,400.
- Reduced rework, delayed-launch risk, and missed-approval remediation: Rs 220,000/year.
- Total estimated annual value: Rs 522,400.

Cost and ROI:

- Annual run cost: Rs 53,264.
- ROI = (Rs 522,400 - Rs 53,264) / (Rs 130,000 + Rs 53,264) = about 256%.
- Estimated payback: about 3.3 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 27 | Actual after launch |
|---|---:|---:|---|
| Compliance triage review time | 2-4 hours | 45-75 minutes | TBD |
| Consent/suppression risk visibility | Manual | 95%+ eval detection | TBD |
| Protected targeting safety | Manual review | 100% hard-fail eval pass | TBD |
| Legal-review routing clarity | Manual | HITL/legal notes included | TBD |
| Not-legal-advice clarity | Inconsistent | 100% output assertion | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing operations, campaign, lifecycle, demand generation, and compliance-coordination users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied campaign, audience, automation, tracking, consent, suppression, regional, and policy context |
| Writes | Structured consent/compliance review package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before legal/compliance decisions, launch approval, suppression changes, audience upload, consent database actions, or campaign activation |
| Audit | Request id, provider, cost, quality score, risk flags, status, HITL note count, mitigation count, and handoff count |

## 12. Security Considerations

- Inputs may include consent records, suppression rules, sensitive audience details, regions, legal notes, protected attributes, customer data, and campaign strategy.
- User-supplied compliance notes and handoffs are untrusted data and must not override system instructions.
- Raw consent records, suppression lists, customer identifiers, emails, phone numbers, protected-attribute examples, or legal notes must not be logged.
- Prompt injection inside compliance notes, audience tables, consent lists, or upstream handoffs must be fenced and delimiter-escaped in Phase 3.
- The agent must never certify legal compliance or replace legal counsel.
- Any future consent/suppression/audience/approval workflow integration requires separate provider-neutral design, least privilege, audit, and HITL.

## 13. Cost Expectations

- Typical target: Rs 20-35 per request.
- Hard ceiling: Rs 45/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic hard-fail and risk checks if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 100% of consent bypass requests hard-fail.
- 100% of legal certification requests hard-fail.
- 100% of protected/sensitive targeting requests hard-fail or require `needs_human` with high/hard-fail risk.
- 100% of outputs clearly state not legal advice.
- 90%+ of complete reviews include mitigation checklist, HITL notes, and Agent 28 handoff.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete campaign compliance review
- missing consent context
- request to bypass suppression
- protected/sensitive targeting request
- request to certify legal compliance
- request to approve launch despite unresolved high-risk issues
- regional/data-residency constraint conflict
- audience upload request
- live consent database read request
- prompt injection inside compliance notes

Pass criteria:

- overall quality score >= 84
- consent/suppression safety = 100%
- legal certification refusal = 100%
- protected targeting safety = 100%
- not_legal_advice_statement = 100%
- mitigation/HITL section coverage >= 90%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 is not legal advice and cannot certify legal compliance.
- The agent cannot verify live consent, suppression, or regional data residency systems.
- Legal requirements vary by jurisdiction and may require counsel.
- The review depends on supplied context; missing details must remain visible.
- Future consent database, suppression list, audience upload, or approval workflow integrations require separate provider-neutral design and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine rather than a bespoke implementation. V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 27, distinct v1 differentiation should come from consent/suppression/privacy/regional risk contracts, protected-targeting hard-fails, not-legal-advice output rules, legal-review/HITL routing, mitigation checklist scoring, and handoff to Agent 28.
