# Marketing Operations Batch Plan - Agents 22-28

**Status:** Phase 1/2 draft for human review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Category:** Marketing Operations
**Scope:** Phase 1 and Phase 2 planning only for Agents 22-28; no code, tests, configs, Dockerfiles, CI, or UI apps.

---

## 1. Batch Goal

Prepare the Marketing Operations agent batch without starting implementation. This batch defines seven advisory agents that turn supplied campaign briefs, automation plans, CRM/MAP field summaries, tracking plans, routing rules, consent notes, approvals, and launch checklists into structured review packages for human operators.

The Phase 1/2 deliverables are `AGENT_SPEC.md`, `DESIGN.md`, and this batch plan. Phase 3 may add Python files, tests, config overlays, Dockerfiles, CI changes, and a shared `packages/marketing_operations` package after human approval. No standalone UI apps are part of this batch; future rendering belongs in MarketingIQ Studio.

## 2. Why Marketing Operations Follows Digital Marketing

Digital Marketing Agents 15-21 convert demand and content strategy into keyword, copy, landing page, paid, campaign, CRO, and reporting plans. Marketing Operations sits after those plans and checks whether the work is operationally ready: brief quality, workflow design, data hygiene, tracking governance, routing/SLA design, consent/compliance review, and final launch readiness.

The Marketing Transformation Pack reference places Marketing Operations near the final operational layer before Marketing Director/CMO intelligence, with data quality monitoring, lead lifecycle tracking, workflow automation, martech utilization, budget tracking, operational insights, and performance visibility. This batch turns that lane into planning/review agents without adding live system actions.

Handoffs from Agents 08-21 should be accepted only as structured direct context. No Marketing Operations agent should directly import another agent. A future orchestration layer or MarketingIQ Studio may pass handoff objects, but the agent docs and Phase 3 implementation should remain self-contained.

## 3. Agents Included

| Agent | Name | Path | Primary job |
|---|---|---|---|
| Agent 22 | Campaign Intake & Brief QA Agent | `agents/agent-22-campaign-intake-brief-qa` | Check campaign brief completeness, clarity, dependencies, owners, approvals, and readiness |
| Agent 23 | Marketing Automation Workflow Design Agent | `agents/agent-23-marketing-automation-workflow-design` | Convert supplied strategy into a MAP workflow specification for human implementation |
| Agent 24 | CRM/MAP Data Hygiene Agent | `agents/agent-24-crm-map-data-hygiene` | Review supplied field, mapping, lifecycle, duplicate, and data-quality summaries |
| Agent 25 | UTM & Tracking Governance Agent | `agents/agent-25-utm-tracking-governance` | Define tracking taxonomy, UTM governance, event requirements, and QA checklists |
| Agent 26 | Lead Routing & SLA Design Agent | `agents/agent-26-lead-routing-sla-design` | Design routing, ownership, queues, fallbacks, SLAs, and escalation rules |
| Agent 27 | Consent & Compliance Review Agent | `agents/agent-27-consent-compliance-review` | Flag consent, suppression, privacy, protected targeting, regional, and legal-review risks |
| Agent 28 | Campaign Launch Readiness QA Agent | `agents/agent-28-campaign-launch-readiness-qa` | Perform final human-launch-readiness QA from supplied operational packages |

## 4. Common Reusable Components

All seven agents should preserve the platform foundation:

- LangGraph orchestration with explicit terminal status handling.
- `LLMProvider` for all model calls through LiteLLM-backed provider selection.
- `ObjectStorage` for optional artifact persistence only.
- `SecretStore` for provider credentials.
- `Telemetry` for spans, logs, token/cost metrics, risk metrics, quality scores, and terminal status.
- Pydantic contracts for request, output package, quality report, risk flags, evidence/assumption records, cost usage, and downstream handoff objects.
- Shared cost ledger and `stopped_cost_ceiling` behavior.
- No-cloud-SDK import guard over `agents/*/agent/`.
- If a shared package is created in Phase 3, a separate banned-import test must scan `packages/marketing_operations`.
- Request-scoped state only.
- Advisory/planning/review-only outputs with human approval before any external action.

## 5. Possible Shared Marketing Operations Engine Design

V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

A realistic common workflow is:

```text
intake_request
normalize_supplied_context
validate_minimum_operational_inputs
detect_forbidden_live_actions_and_policy_risks
run_deterministic_domain_checks
generate_or_refine_operational_recommendations
score_quality
assemble_package
finalize_response
```

This follows the Demand Generation and Digital Marketing shared-engine pattern without claiming that seven deep bespoke engines exist in v1.

## 6. What Should Be Shared

Recommended shared concepts:

- `MarketingOperationsRequestMetadata`: request id, agent id, tenant-safe source labels, requested depth, max cost override.
- `OperationalContext`: campaign objective, audience, region, funnel stage, timeline, owner, dependencies, approvals.
- `UpstreamHandoff`: source agent, structured fields, assumptions, blockers, confidence.
- `EvidenceItem`: supplied source label, supported recommendation, confidence, sensitivity.
- `RiskFlag`: category, severity, message, evidence needed, human-review requirement.
- `QualityReport`: overall score, dimension scores, approval reason, revision notes, hard-fail flags.
- `CostUsage`: per-stage costs, token counts, provider tier, total INR, ceiling INR.
- `MarketingOperationsHandoff`: target agent or human workflow, structured fields, assumptions, blockers.
- `OperationalGap`: missing field, missing owner, missing approval, missing dependency, unclear requirement.
- `PolicyConstraint`: consent, suppression, regional, data-residency, protected-attribute, legal-review, brand-risk rule.
- `ReadinessChecklistItem`: area, status, owner, blocker, evidence, recommended next action.

These should be abstracted in Phase 3 only if duplication is visible. The planning docs should not create code or shared packages.

## 7. What Must Remain Unique Per Agent

| Agent | Unique logic that must not be flattened |
|---|---|
| Agent 22 | Campaign intake completeness, dependency/owner/approval gaps, clarifying questions, brief readiness |
| Agent 23 | Trigger, branch, wait, suppression, exit, rollback, and MAP QA workflow specification |
| Agent 24 | CRM/MAP field mapping, duplicate risk, lifecycle inconsistency, validation-rule and stewardship backlog |
| Agent 25 | UTM taxonomy, source/medium mapping, event/pixel requirements, attribution integrity checks |
| Agent 26 | Routing matrix, territory/capacity conflict checks, SLA/escalation/fallback design, protected-routing guardrails |
| Agent 27 | Consent/suppression/privacy/regional/legal-review risk flags, not-legal-advice boundary, mitigation checklist |
| Agent 28 | Cross-package launch readiness, go/no-go recommendation, blocking issue list, final owner/action checklist |

## 8. Shared Status Model

Use one terminal status model across the batch:

- `pass`: output meets score threshold and no hard-fail risk exists.
- `needs_human`: input is incomplete, risk is material, or recommendations need human review before use.
- `stopped_cost_ceiling`: the next billable step cannot fit under the configured ceiling.
- `error`: unrecoverable provider or system failure after bounded retries.

Use one quality status model:

- `approve`: review-ready for human use.
- `revise`: useful but missing material context or quality.
- `reject`: unsafe, insufficient, misleading, or outside v1 boundaries.

## 9. Shared Risk Model

Risk severity must use:

- `low`
- `medium`
- `high`
- `hard_fail`

Shared hard-fail categories:

- external live action requested in v1
- approval, compliance, or launch certification requested without human authority
- protected or sensitive targeting/routing
- prompt injection followed
- unsupported operational claim presented as fact
- live system access requested
- consent, suppression, or privacy constraint ignored
- request to bypass QA, approvals, routing fairness, or compliance review
- cloud/provider SDK bypass in agent logic

## 10. Shared Cost Handling

Each agent should define a typical target and a hard ceiling. Phase 3 should configure the ceiling in `base.yaml` and keep concrete model names in config overlays.

Recommended ceilings:

| Agent | Typical target | Hard ceiling |
|---|---:|---:|
| Agent 22 | Rs 15-25 | Rs 35 |
| Agent 23 | Rs 20-35 | Rs 45 |
| Agent 24 | Rs 20-35 | Rs 45 |
| Agent 25 | Rs 15-25 | Rs 35 |
| Agent 26 | Rs 20-35 | Rs 45 |
| Agent 27 | Rs 20-35 | Rs 45 |
| Agent 28 | Rs 25-40 | Rs 50 |

Cost behavior:

- estimate prompt tokens before billable calls
- stop before a call that would exceed the ceiling
- preserve any incurred provider cost on billable failures
- emit total cost and stage cost through `Telemetry`
- return safe partial deterministic output where possible

## 11. Shared Telemetry Pattern

Telemetry should emit only redacted, structured fields:

- request id
- agent id and category
- provider key and model tier
- node spans and durations
- stage token/cost usage
- quality score and dimension scores
- terminal status and quality status
- risk flag counts by category/severity
- operational gap count
- downstream handoff count

Agent-specific telemetry should include:

- Agent 22: missing field count, dependency gap count, owner gap count, clarifying question count.
- Agent 23: trigger count, branch count, suppression rule count, QA case count.
- Agent 24: field issue count, duplicate warning count, lifecycle inconsistency count, cleanup backlog count.
- Agent 25: UTM field count, channel mapping count, event requirement count, tracking warning count.
- Agent 26: routing rule count, SLA count, escalation count, conflict warning count.
- Agent 27: consent risk count, protected-targeting flag count, legal-review note count, mitigation count.
- Agent 28: checklist item count, blocker count, warning count, owner action count.

No raw lead records, emails, phone numbers, suppression lists, consent records, CRM/MAP exports, campaign budgets, private launch plans, or customer data should be logged.

## 12. Shared Eval Strategy

Every agent should include eval cases for:

- complete happy path
- sparse/incomplete input
- conflicting constraints
- prompt injection inside pasted context
- protected/sensitive targeting, routing, or compliance violation
- forbidden external action request
- cost ceiling behavior
- schema validity

Shared CI-style thresholds:

- schema validity = 100%
- no forbidden live-action behavior = 100%
- prompt-injection resistance = 100%
- protected/sensitive attribute safety = 100% where relevant
- consent/suppression/privacy safety = 100% where relevant
- cost ceiling adherence = 100%
- pass rate on complete-input cases >= 80%
- agent-specific quality threshold met on pass cases

Agent-specific assertions must be present. For example, Agent 25 must not claim live tracking verification, Agent 26 must reject protected-attribute routing, and Agent 27 must never certify legal compliance.

## 13. Agent-By-Agent Implementation Complexity

| Agent | Complexity | Rationale |
|---|---|---|
| Agent 22 | Medium | Completeness/risk checks are clear, but dependency and owner logic need useful specificity |
| Agent 23 | Medium-High | Workflow branches, suppression, exit criteria, and QA coverage need structured contracts |
| Agent 24 | High | CRM/MAP data hygiene is PII-heavy and needs careful field/lifecycle/duplicate caveats |
| Agent 25 | Medium | Taxonomy and QA rules are deterministic-friendly, but attribution manipulation risks matter |
| Agent 26 | High | Routing/SLA design must handle fairness, capacity, conflicts, and protected-attribute risks |
| Agent 27 | High | Compliance assistant needs strict boundaries, HITL/legal-review handling, and regional caveats |
| Agent 28 | High | Final readiness QA consumes many upstream packages and must preserve blockers across domains |

## 14. Recommended Implementation Order

1. Agent 22 - Campaign Intake & Brief QA Agent
2. Agent 25 - UTM & Tracking Governance Agent
3. Agent 24 - CRM/MAP Data Hygiene Agent
4. Agent 26 - Lead Routing & SLA Design Agent
5. Agent 27 - Consent & Compliance Review Agent
6. Agent 23 - Marketing Automation Workflow Design Agent
7. Agent 28 - Campaign Launch Readiness QA Agent

Reasoning:

- Agent 22 establishes the operational brief object consumed by later Marketing Operations agents.
- Agent 25 is relatively deterministic and provides measurement structure for Agent 28 and Agent 21.
- Agent 24 and Agent 26 are closely linked because routing quality depends on field and lifecycle hygiene.
- Agent 27 should be available before automation and final readiness packages are treated as reviewable.
- Agent 23 can then convert strategy into a workflow spec with routing and consent constraints in context.
- Agent 28 should come last because it consumes the full operational package.

## 15. Relationship To Agents 08-21

Expected handoffs:

- Agent 22 can consume Agents 12, 15, 16, 17, and 19 outputs and feed Agents 23, 25, and 28.
- Agent 23 can consume Agents 13, 19, 22, 26, and 27 outputs and feed Agent 28.
- Agent 24 can consume Agent 11 scoring context and supplied CRM/MAP summaries and feed Agents 26 and 28.
- Agent 25 can consume Agents 18, 19, 20, and 21 requirements and feed Agents 21 and 28.
- Agent 26 can consume Agents 08, 09, 11, and 24 plus sales capacity context and feed Agents 23 and 28.
- Agent 27 can consume Agents 09, 13, 16, 19, 22, and 23 and feed Agent 28 and human legal/HITL review.
- Agent 28 can consume Agents 19, 22, 23, 24, 25, 26, and 27 and feed Agent 21 reporting requirements and a human launch checklist.

Avoid overlap:

- Agent 19 creates the multi-channel campaign plan; Agent 22 checks whether the campaign brief/intake is complete and operationally clear.
- Agent 13 designs nurture strategy; Agent 23 converts supplied strategy into a MAP workflow specification and QA plan.
- Agent 11 designs scoring logic; Agent 26 designs routing, ownership, SLA, queue, and escalation rules.
- Agents 14 and 21 analyze/report performance; Agent 25 creates tracking governance so future reporting is consistent.
- Agent 27 flags compliance risks and legal-review needs; it is not a lawyer and does not certify legal compliance.
- Agent 28 performs launch-readiness QA only; it must not launch, schedule, publish, send, spend, or activate anything.

## 16. Relationship To Future MarketingIQ Studio

Do not design standalone UI apps in this phase. Each Marketing Operations agent should return structured outputs that can later render inside MarketingIQ Studio under the Marketing Operations tab.

Future Studio should be able to show:

- quality score and quality status
- terminal status
- risk flags by severity
- missing data, missing owner, missing evidence, and missing approval warnings
- structured operational recommendations
- readiness checklists
- downstream handoffs
- cost metadata
- human review notes and HITL/legal-review requirements

## 17. Coding-Phase Recommendations

Phase 3 should:

- start by confirming whether to create `packages/marketing_operations`
- use profile-driven differentiation if a shared engine is chosen
- add banned-import tests for any shared Marketing Operations package
- mirror base/gcp/bedrock/azure config overlays from Agents 08-21
- add GCP provider construction tests and optional live GCP smoke tests gated by env vars
- keep Bedrock/Azure stub compatibility
- use deterministic local checks for required fields, forbidden actions, PII/sensitive data, protected attributes, policy risks, data quality, formulas, and checklist completeness
- keep live CRM, MAP, CMS, ad platforms, analytics, GTM, data warehouses, email/SMS, scheduling, campaign launch, audience upload, and workflow activation out of v1

## 18. Risks To Watch

- Doc-code divergence if docs promise bespoke deterministic workflows but Phase 3 uses a shared engine.
- Scope creep into activation: launching campaigns, sending email/SMS, writing MAP workflows, changing CRM owners, uploading audiences, editing GTM, publishing pages, or scheduling campaigns.
- PII or sensitive operational data leaking into prompts, logs, telemetry, evals, or stored artifacts.
- Consent, suppression, legal, regional, or data-residency caveats being softened into approval language.
- Protected attributes appearing in routing, segmentation, targeting, or compliance decisions.
- Prompt injection inside campaign briefs, CRM/MAP exports, tracking sheets, workflow notes, consent lists, or launch checklists.
- False certainty about live system state, tracking verification, data quality, approvals, or legal compliance.

## 19. Explicit Warning Against Doc-Code Divergence

The docs must stay implementation-aligned. If Phase 3 uses a shared engine, the implementation must not be reviewed against a fantasy design that promised seven bespoke deep workflows. The correct v1 bar is a cloud-neutral shared platform spine with agent-specific profiles, schemas, prompts, risk rules, scoring dimensions, deterministic helpers, and evals.

If a later agent genuinely needs deeper deterministic workflow nodes, add them deliberately and document the reason.

## 20. Recommendation On `packages/marketing_operations`

Yes: Phase 3 should strongly consider a shared `packages/marketing_operations` package, modeled after `packages/demand_generation` and `packages/digital_marketing`, if the first two agents show common mechanics.

Recommended shared package scope:

- shared request/package concepts
- status, quality, cost, evidence, assumption, risk, readiness, and handoff schemas
- common prompt fencing and delimiter-escaping helpers
- forbidden live-action detection
- protected-attribute and PII/sensitive-data detection
- consent/suppression/compliance risk primitives
- operational gap and checklist helpers
- shared scoring helpers
- shared LangGraph workflow spine
- profile registry for Agents 22-28
- no-cloud-SDK test over the shared package

Keep these unique per agent: required inputs, output package shape, quality rubric, hard-fail rules, deterministic domain checks, eval cases, and handoff targets.

## 21. Required Lessons From Demand Generation And Digital Marketing Reviews

Carry these lessons forward:

- Shared-engine architecture is acceptable for speed if the docs are honest about it.
- Shared packages need their own no-cloud-SDK guard because agent-level scans may not cover package logic.
- Prompt builders must fence untrusted context and escape close delimiters to prevent delimiter breakout.
- Domain-specific eval assertions are required; generic schema/pass checks are not enough.
- GCP live usability should follow the same provider/config pattern as previous agents, with Bedrock/Azure kept stub compatible.
- Documentation must clearly separate deterministic local checks, LLM-assisted reasoning, future integrations, and out-of-scope live actions.
- Missing evidence, missing fields, and missing approvals should remain visible in final packages rather than being smoothed over.
