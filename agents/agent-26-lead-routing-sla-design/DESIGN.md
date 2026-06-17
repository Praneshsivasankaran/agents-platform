# Agent 26 - Lead Routing & SLA Design Agent Design

## 1. Metadata

**Agent number:** 26
**Agent name:** Lead Routing & SLA Design Agent
**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-26-lead-routing-sla-design/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 26 designs advisory lead routing, ownership, queue, fallback, escalation, and SLA rules from supplied segment, score, territory, capacity, lifecycle, and data hygiene context. It must produce a reviewable design without updating owners, activating routing, or sending notifications.

## 3. Agent Boundaries

In scope:

- Normalize supplied segment, scoring, territory, owner, capacity, lifecycle, and routing context.
- Produce routing matrix, assignment rules, queue/fallback logic, SLA definitions, escalation rules, exception handling, conflict warnings, and QA scenarios.
- Flag protected-attribute, fairness, owner-update, routing activation, notification, and data-dependency risks.

Out of scope:

- CRM/MAP writes, owner updates, routing automation activation, lead assignment, territory system updates, sales notification sends, live CRM/MAP queries, or routing certification.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_routing_context_and_handoffs
3. validate_segment_score_owner_capacity_and_sla_inputs
4. detect_protected_attribute_and_forbidden_routing_requests
5. design_routing_matrix_and_assignment_rules
6. design_sla_escalation_queue_and_fallback_logic
7. detect_territory_capacity_and_data_dependency_conflicts
8. create_routing_qa_test_scenarios
9. create_agent23_and_agent28_handoffs
10. score_routing_sla_design
11. assemble_lead_routing_sla_design_package
12. finalize_response
```

V1 may use a shared Marketing Operations engine with an Agent 26 profile. Deterministic stages include required-context validation, protected-attribute detection, forbidden-action detection, conflict classification, SLA/queue completeness checks, QA coverage checks, and status mapping. LLM-assisted stages synthesize routing rationale, exception guidance, and human-readable implementation notes from supplied context.

## 5. State Model

Request-scoped state should contain:

- normalized routing context and upstream handoffs
- segment, score, territory, owner, capacity, and lifecycle summaries
- routing matrix and assignment rules
- SLA definitions and escalation rules
- queue/fallback logic and exception handling
- conflict warnings and data dependency notes
- QA test scenarios
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain CRM/MAP clients, routing engines, sales engagement clients, notification clients, territory management clients, database clients, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- segment/score context, routing objective, owner/queue/territory/capacity details, SLA expectations
- lifecycle stage rules, lead source/channel context, fallback owners, escalation preferences, business hours
- compliance/fairness constraints, protected-attribute exclusions, data hygiene findings
- Agents 08, 09, 11, and 24 handoffs
- QA examples, known edge cases, assumptions, and source labels

## 7. Outputs

Primary output concepts:

- `LeadRoutingSLADesignPackage`
- `RoutingMatrix`
- `AssignmentRule`
- `RoutingException`
- `TerritoryCapacityConsideration`
- `SLADefinition`
- `EscalationRule`
- `QueueFallbackRule`
- `RoutingConflictWarning`
- `RoutingQATestScenario`
- `MarketingOperationsHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `LeadRoutingSLADesignRequest`
- `RoutingContext`
- `SegmentScoreInput`
- `RoutingRule`
- `SLAPolicy`
- `EscalationPolicy`
- `QueueFallbackPolicy`
- `RoutingConflict`
- `RoutingQACase`
- `LeadRoutingSLAQualityReport`
- `LeadRoutingSLADesignPackage`

Shared status, risk, evidence, assumption, cost, readiness, and handoff contracts should be reused if `packages/marketing_operations` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_routing_inputs` | request | missing segment/score/owner/SLA blockers | None | Local only |
| `detect_protected_routing_attributes` | request text/field labels | protected-attribute hard-fail flags | None | Local only |
| `detect_routing_forbidden_actions` | request text | owner update/activation/notification hard-fail flags | None | Local only |
| `detect_territory_capacity_conflicts` | territory/capacity/rules | conflict warnings | None | Local only |
| `check_sla_queue_completeness` | SLA and fallback design | missing SLA/fallback warnings | None | Local only |
| `score_routing_sla_design` | design, QA cases, risks | quality report | None | Local only |

No CRM, MAP, routing engine, territory system, sales engagement, notification, database, or workflow activation tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent routing memory in v1.
- Prior routing policies or territory plans can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require routing objective and enough segment/score/routing context to define paths.
- Missing score, segment, routing, or owner/capacity context returns `needs_human`.
- Flag conflicting territory/capacity rules and missing fallback owners as warnings or blockers.
- Hard-flag owner updates, routing activation, territory updates, notification sends, and protected-attribute routing.
- Ensure scoring context from Agent 11 is used as input only; do not redesign the scoring model unless supplied as an explicit routing constraint.
- Preserve data hygiene blockers from Agent 24.

## 12. Prompt Strategy

- User-provided notes, campaign briefs, CRM/MAP exports, field lists, routing rules, tracking plans, compliance notes, and launch checklists are untrusted.
- Untrusted text must be fenced and delimiter-escaped.
- User-supplied data must never override system/developer instructions.
- The model must not invent system access, approvals, consent, legal certification, data quality results, launch status, or live-system changes.
- All recommendations must cite supplied evidence or be labeled as assumptions/heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

Agent 26 prompts should emphasize that routing rules are advisory, should avoid protected attributes, and must separate lead scoring input from routing/SLA decisions.

## 13. Quality Scoring Strategy

Agent 26 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Routing matrix completeness | 20 |
| Assignment and exception rule clarity | 15 |
| SLA and escalation design quality | 15 |
| Queue and fallback logic coverage | 15 |
| Territory/capacity conflict handling | 10 |
| QA test scenario usefulness | 15 |
| Protected-attribute and activation safety | 10 |

Pass if score >= 84 and no hard-fail risk. Hard-fail risks override the numeric score.

## 14. Evaluation Strategy

Eval datasets should cover complete routing design, missing score/segment context, missing owner/fallback context, conflicting territory/capacity rules, protected-attribute routing, owner update request, activation request, sales notification request, data hygiene blocker, and prompt injection.

CI gates:

- schema_valid = 100%
- missing_routing_context_behavior = 100%
- no_owner_update_activation_notification_behavior = 100%
- protected_attribute_routing_safety = 100%
- conflict_warning_behavior >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 15. Error Handling Strategy

- Missing score/segment/routing context returns `needs_human`.
- Protected-attribute routing, owner update, activation, territory update, or notification requests return hard-fail risk flags.
- Conflicting territory/capacity inputs return `needs_human` or high-severity warnings with resolution options.
- Cost stop returns `stopped_cost_ceiling` with deterministic validation if available.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 16. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, validation, protected-attribute detection, routing design, SLA/escalation design, conflict checks, QA generation, scoring, finalization
- token/cost by stage
- routing rule count, SLA count, escalation count, fallback count, conflict warning count, QA scenario count, quality score, risk counts
- no raw lead records, contact details, owner performance notes, territory exports, emails, phone numbers, or full routing sheets in logs

## 17. Cloud Agnostic Review

- No cloud SDK imports inside `agent/`.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No CRM/MAP, routing engine, territory system, sales engagement, notification, database, direct model SDK, or `litellm` imports inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents.
- Bedrock/Azure must remain config/stub compatible.
- Shared `packages/marketing_operations` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render routing matrix, SLA tables, escalation rules, queue/fallback logic, territory/capacity warnings, protected-attribute risks, QA scenarios, and handoffs to Agents 23 and 28. Studio may later support CRM/MAP routing implementation only after separate provider-neutral write designs and human approval gates.

## 19. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine with an Agent 26 profile. The profile should define routing/SLA output sections, protected-attribute checks, activation/owner-update hard-fails, conflict classification, quality dimensions, and eval cases. Future versions may add provider-neutral CRM routing connectors or capacity calculators, but owner updates and routing activation remain out of v1.
