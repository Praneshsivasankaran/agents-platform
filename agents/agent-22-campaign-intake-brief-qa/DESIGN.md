# Agent 22 - Campaign Intake & Brief QA Agent Design

## 1. Metadata

**Agent number:** 22
**Agent name:** Campaign Intake & Brief QA Agent
**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-22-campaign-intake-brief-qa/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 22 checks supplied campaign briefs for completeness, clarity, operational feasibility, owner/dependency gaps, approval gaps, and v1-forbidden action requests. It returns a structured QA package that helps a human decide whether the brief can move into execution planning.

## 3. Agent Boundaries

In scope:

- Normalize supplied campaign brief, intake notes, and upstream handoffs.
- Check objective, audience, offer, timeline, channel, owner, approval, assets, measurement, and consent context.
- Generate missing-field warnings, unclear requirement flags, dependency/owner/approval gaps, clarifying questions, and readiness recommendation.
- Flag project/task creation, launch, scheduling, publishing, sending, and approval-bypass requests.

Out of scope:

- Creating project tasks, updating calendars, approving campaigns, launching campaigns, scheduling posts, sending emails/SMS, publishing pages, writing workflows, modifying CRM/MAP/CMS/ad platforms, or certifying operational approval.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_brief_and_handoffs
3. validate_required_campaign_context
4. detect_owner_dependency_asset_and_approval_gaps
5. detect_tracking_consent_and_operational_risks
6. generate_clarifying_questions
7. detect_forbidden_live_actions
8. score_brief_readiness
9. assemble_campaign_intake_qa_package
10. finalize_response
```

V1 may use a shared Marketing Operations engine with an Agent 22 profile. Deterministic stages include required-field validation, forbidden-action detection, owner/dependency/asset/approval gap checks, status mapping, and score support. LLM-assisted stages synthesize clearer requirement summaries, clarifying questions, and readiness rationale from supplied evidence.

## 5. State Model

Request-scoped state should contain:

- normalized campaign brief
- upstream handoff summaries
- required-field validation results
- owner, dependency, approval, asset, tracking, and consent gaps
- forbidden-action and policy risk flags
- clarifying questions
- readiness recommendation
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain project-management, calendar, MAP, CRM, CMS, ad platform, analytics, scheduling, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- campaign objective, target audience, offer/key message, channel/campaign type, timeline or launch window
- requester, owner, stakeholders, approval path, budget, region, product, funnel stage
- asset inventory, creative/page/copy notes, measurement requirements, consent/suppression constraints
- Agents 12, 15, 16, 17, and 19 handoffs
- known risks, dependencies, blockers, and source labels

## 7. Outputs

Primary output concepts:

- `CampaignIntakeBriefQAPackage`
- `NormalizedCampaignBrief`
- `BriefCompletenessScore`
- `MissingInformationWarning`
- `UnclearRequirementFlag`
- `DependencyGap`
- `OwnerApprovalGap`
- `AssetGap`
- `TrackingMeasurementGap`
- `ClarifyingQuestion`
- `MarketingOperationsHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `CampaignIntakeBriefQARequest`
- `CampaignBriefContext`
- `BriefFieldAssessment`
- `OperationalGap`
- `ApprovalRequirement`
- `ClarifyingQuestion`
- `CampaignIntakeBriefQAQualityReport`
- `CampaignIntakeBriefQAPackage`

Shared status, risk, evidence, assumption, cost, readiness, and handoff contracts should be reused if `packages/marketing_operations` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_campaign_brief_inputs` | request | missing required fields and blockers | None | Local only |
| `detect_owner_dependency_asset_gaps` | normalized brief | operational gap list | None | Local only |
| `detect_approval_and_tracking_gaps` | normalized brief | approval/tracking warnings | None | Local only |
| `detect_forbidden_intake_actions` | request text | hard-fail risk flags | None | Local only |
| `score_brief_readiness` | brief, gaps, risks | quality report | None | Local only |
| `build_handoffs` | final package | structured handoffs | None | Local only |

No project-management, calendar, MAP, CRM, CMS, ad platform, analytics, email, SMS, scheduling, or publishing tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No long-term campaign intake memory in v1.
- Prior briefs or upstream outputs can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require campaign objective and target audience; missing either returns `needs_human`.
- Require at least one offer/message and some timing/channel context for an approval-quality pass.
- Flag missing owners, approvals, dependencies, asset inventory, tracking requirements, or consent constraints as warnings or blockers.
- Hard-flag requests to create tasks, approve automatically, launch, schedule, send, publish, or bypass approvals.
- Preserve hard-fail risks in the final package even if other fields are complete.
- Missing-data behavior should produce clarifying questions rather than invented assumptions.

## 12. Prompt Strategy

- User-provided notes, campaign briefs, CRM/MAP exports, field lists, routing rules, tracking plans, compliance notes, and launch checklists are untrusted.
- Untrusted text must be fenced and delimiter-escaped.
- User-supplied data must never override system/developer instructions.
- The model must not invent system access, approvals, consent, legal certification, data quality results, launch status, or live-system changes.
- All recommendations must cite supplied evidence or be labeled as assumptions/heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

Agent 22 prompts should focus the model on clarifying ambiguous brief language, grouping questions by operational blocker, and avoiding any language that sounds like final campaign approval.

## 13. Quality Scoring Strategy

Agent 22 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Required brief completeness | 25 |
| Objective/audience/offer clarity | 15 |
| Timeline, owner, and approval readiness | 15 |
| Asset and dependency visibility | 15 |
| Tracking and measurement readiness | 10 |
| Clarifying question usefulness | 10 |
| Scope and approval safety | 10 |

Pass if score >= 82 and no hard-fail risk. Hard-fail risks override the numeric score.

## 14. Evaluation Strategy

Eval datasets should cover complete briefs, missing objective, missing audience, missing owner, missing approvals, vague timeline, request to create project tasks, auto-approval request, launch/schedule/send/publish request, consent bypass, and prompt injection.

CI gates:

- schema_valid = 100%
- missing_objective_or_audience_behavior = 100%
- no_task_creation_or_activation_behavior = 100%
- approval_bypass_safety = 100%
- required_section_coverage >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 15. Error Handling Strategy

- Missing campaign objective or audience returns `needs_human`.
- Forbidden live-action or approval-bypass requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with deterministic missing-field/gap checks if available.
- Provider failure returns `error` with redacted category and preserved cost usage.
- Conflicting stakeholder requirements return `needs_human` with resolution questions.

## 16. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, validation, gap detection, risk detection, question generation, scoring, finalization
- token/cost by stage
- missing field count, owner gap count, dependency gap count, approval gap count, asset gap count, clarifying question count, quality score, risk counts
- no raw campaign briefs, budgets, launch plans, account lists, PII, suppression notes, or approval comments in logs

## 17. Cloud Agnostic Review

- No cloud SDK imports inside `agent/`.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No project-management, calendar, MAP, CRM, CMS, ad platform, analytics, scheduler, email/SMS, direct model SDK, or `litellm` imports inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents.
- Bedrock/Azure must remain config/stub compatible.
- Shared `packages/marketing_operations` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render Agent 22 as the Marketing Operations intake gate: brief completeness score, missing fields, owner/dependency/approval gaps, clarifying questions, risk flags, cost, and structured handoffs to Agents 23, 25, and 28. Studio may later route approved brief sections to planning workflows only after separate integration design and human approval.

## 19. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine with an Agent 22 profile. The profile should define required brief fields, brief-readiness output sections, forbidden project/launch/approval actions, quality dimensions, and eval cases. Future versions may add deeper deterministic checks for resource capacity or calendar feasibility, but live project/task/calendar operations remain out of v1.
