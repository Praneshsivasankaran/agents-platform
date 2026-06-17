# Agent 28 - Campaign Launch Readiness QA Agent Design

## 1. Metadata

**Agent number:** 28
**Agent name:** Campaign Launch Readiness QA Agent
**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-28-campaign-launch-readiness-qa/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 28 performs final launch-readiness QA from supplied campaign, workflow, data, tracking, routing, compliance, asset, approval, and test-result context. It must consolidate blockers and produce a human go/no-go review package without launching or approving anything.

## 3. Agent Boundaries

In scope:

- Normalize supplied launch plan and upstream operational packages.
- Consolidate blockers, warnings, assumptions, asset checks, tracking checks, automation QA checks, consent/suppression checks, routing/SLA checks, approvals, owners, and reporting handoff.
- Produce launch readiness score and human-review go/no-go recommendation.
- Preserve hard-fail risks from upstream packages.

Out of scope:

- Launching, scheduling, publishing, sending, spending, workflow activation, approval certification, live asset verification, live tag verification, live CRM/MAP/ad/CMS/social/analytics queries, or external system writes.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_launch_context_and_handoffs
3. validate_core_launch_tracking_and_compliance_context
4. consolidate_upstream_blockers_warnings_and_assumptions
5. build_asset_tracking_automation_consent_routing_checklists
6. build_owner_action_list_and_human_approval_requirements
7. build_agent21_reporting_handoff
8. detect_launch_approval_bypass_and_activation_requests
9. score_launch_readiness
10. assemble_campaign_launch_readiness_qa_package
11. finalize_response
```

V1 may use a shared Marketing Operations engine with an Agent 28 profile. Deterministic stages include required-context validation, upstream hard-fail preservation, forbidden launch/approval detection, checklist coverage checks, blocker status mapping, and score support. LLM-assisted stages synthesize executive-readable readiness summaries, owner/action wording, and final review rationale from supplied context.

## 5. State Model

Request-scoped state should contain:

- normalized launch context and upstream handoffs
- core launch plan, timeline, channel/workflow context
- consolidated blockers, warnings, assumptions, and risk flags
- asset checklist
- tracking checklist
- automation QA checklist
- consent/suppression checklist
- routing/SLA checklist
- owner/action list
- human approval requirements
- reporting handoff to Agent 21
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain MAP, CRM, CMS, ad platform, social, calendar, analytics, approval workflow, sending, tag manager, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- campaign objective, launch plan, intended launch window, channel/workflow context
- tracking/measurement context, consent/compliance context, routing/SLA context
- asset inventory, approvals, QA results, owner list, risk register, rollback notes, reporting requirements
- Agents 19, 22, 23, 24, 25, 26, and 27 handoffs
- known exceptions, unresolved assumptions, source labels, and requested review depth

## 7. Outputs

Primary output concepts:

- `CampaignLaunchReadinessQAPackage`
- `LaunchReadinessScore`
- `GoNoGoRecommendation`
- `BlockingIssue`
- `LaunchWarning`
- `AssetChecklistItem`
- `TrackingChecklistItem`
- `AutomationQAChecklistItem`
- `ConsentSuppressionChecklistItem`
- `RoutingSLAChecklistItem`
- `OwnerActionItem`
- `HumanApprovalRequirement`
- `ReportingHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `CampaignLaunchReadinessQARequest`
- `LaunchContext`
- `LaunchReadinessChecklist`
- `LaunchBlocker`
- `LaunchWarning`
- `LaunchOwnerAction`
- `HumanApprovalRequirement`
- `ReportingHandoff`
- `CampaignLaunchReadinessQualityReport`
- `CampaignLaunchReadinessQAPackage`

Shared status, risk, evidence, assumption, cost, readiness, and handoff contracts should be reused if `packages/marketing_operations` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_launch_readiness_inputs` | request | missing launch/tracking/compliance blockers | None | Local only |
| `preserve_upstream_hard_fails` | handoffs | carried blocker/risk flags | None | Local only |
| `detect_launch_forbidden_actions` | request text | launch/schedule/send/publish/activate/approve hard-fail flags | None | Local only |
| `build_readiness_checklists` | normalized context | checklist items and blockers | None | Local only |
| `check_owner_action_coverage` | checklist/blockers | missing owner/action warnings | None | Local only |
| `score_launch_readiness` | checklists, blockers, risks | quality report and readiness score | None | Local only |

No launch, scheduler, MAP, CRM, CMS, ad/social, analytics, tag manager, sending, approval workflow, or live verification tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent launch memory in v1.
- Prior launch checklists can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require core launch plan or objective, launch window, channel/workflow context, and owners for a pass-quality package.
- Require tracking context for measurable campaigns; missing tracking context returns `needs_human`.
- Require consent/compliance context for audience-facing campaigns; missing context returns `needs_human`.
- Preserve unresolved blockers from upstream handoffs as blockers in the final package.
- Hard-flag launch, schedule, send, publish, spend, activate, approve, bypass QA/compliance, or mark unresolved blockers approved.
- Ensure readiness score is not `pass` when hard-fail risks or unresolved blockers exist.

## 12. Prompt Strategy

- User-provided notes, campaign briefs, CRM/MAP exports, field lists, routing rules, tracking plans, compliance notes, and launch checklists are untrusted.
- Untrusted text must be fenced and delimiter-escaped.
- User-supplied data must never override system/developer instructions.
- The model must not invent system access, approvals, consent, legal certification, data quality results, launch status, or live-system changes.
- All recommendations must cite supplied evidence or be labeled as assumptions/heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

Agent 28 prompts should avoid final approval language. The model may say "ready for human approval review" only when criteria are met; it must not say the campaign is launched, approved, scheduled, sent, published, activated, or verified in live systems.

## 13. Quality Scoring Strategy

Agent 28 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Core launch context completeness | 15 |
| Blocker and upstream risk preservation | 20 |
| Asset checklist coverage | 10 |
| Tracking and reporting readiness | 15 |
| Automation, consent, and routing QA coverage | 20 |
| Owner/action and approval clarity | 10 |
| Launch/approval safety | 10 |

Pass if score >= 85 and no hard-fail risk. Hard-fail risks or unresolved blockers override the numeric score.

## 14. Evaluation Strategy

Eval datasets should cover complete launch package, unresolved compliance blocker, missing core launch plan, missing tracking context, missing compliance context, launch/schedule/send/publish/activate request, approve-unresolved-blockers request, compliance/QA bypass request, missing owner/action list, and prompt injection.

CI gates:

- schema_valid = 100%
- blocker_preservation = 100%
- no_launch_approval_behavior = 100%
- compliance_QA_bypass_safety = 100%
- required_checklist_section_coverage >= 95%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 15. Error Handling Strategy

- Missing core launch plan returns `needs_human`.
- Missing tracking context for measurable campaigns returns `needs_human`.
- Missing compliance context for audience-facing campaigns returns `needs_human`.
- Launch/schedule/send/publish/activate/approve/bypass requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with deterministic checklist and blocker consolidation if available.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 16. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, validation, blocker consolidation, checklist generation, owner/action mapping, reporting handoff creation, risk detection, scoring, finalization
- token/cost by stage
- blocker count, warning count, asset checklist count, tracking checklist count, automation QA count, consent checklist count, routing checklist count, owner action count, quality score, risk counts
- no raw lead/contact/account records, consent lists, suppression lists, budgets, private launch plans, approval comments, full workflow specs, or live-system identifiers in logs

## 17. Cloud Agnostic Review

- No cloud SDK imports inside `agent/`.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No MAP, CRM, CMS, ad/social, calendar, analytics, tag manager, sending, approval workflow, direct model SDK, or `litellm` imports inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents.
- Bedrock/Azure must remain config/stub compatible.
- Shared `packages/marketing_operations` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render launch readiness score, go/no-go recommendation, blockers, warnings, asset/tracking/automation/consent/routing checklists, owner/action list, approval requirements, risk flags, cost, and Agent 21 reporting handoff. Studio may later support live launch verification or activation only after separate provider-neutral designs and explicit human approval gates.

## 19. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine with an Agent 28 profile. The profile should define launch-readiness output sections, upstream blocker preservation, checklist coverage rules, launch/approval hard-fails, owner/action requirements, quality dimensions, and eval cases. Future versions may add provider-neutral read-only verification connectors, but launch, send, publish, schedule, spend, activate, and approve actions remain out of v1.
