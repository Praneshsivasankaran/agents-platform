# Agent 23 - Marketing Automation Workflow Design Agent Design

## 1. Metadata

**Agent number:** 23
**Agent name:** Marketing Automation Workflow Design Agent
**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-23-marketing-automation-workflow-design/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 23 turns supplied campaign, nurture, routing, and consent context into a structured marketing automation workflow specification for human MAP implementation. It must define the workflow clearly without creating, activating, sending, importing, or updating anything in a live system.

## 3. Agent Boundaries

In scope:

- Normalize campaign/nurture strategy, audience, trigger, cadence, assets, data dependencies, routing, and consent context.
- Design workflow map, entry criteria, branch logic, wait steps, suppression/exclusion rules, exit criteria, QA cases, rollback notes, and monitoring notes.
- Flag missing triggers, unclear audience criteria, missing suppression, data dependencies, and forbidden activation/send/import requests.

Out of scope:

- MAP writes, workflow activation, email/SMS sends, contact imports, list uploads, CRM updates, webhook/API execution, live consent database reads, or live workflow verification.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_strategy_and_handoffs
3. validate_trigger_audience_goal_and_consent
4. design_workflow_steps_and_branches
5. define_wait_steps_suppression_and_exits
6. identify_assets_fields_and_data_dependencies
7. create_qa_test_cases
8. create_rollback_and_monitoring_notes
9. detect_activation_send_import_and_consent_bypass_risks
10. score_workflow_design
11. assemble_workflow_design_package
12. finalize_response
```

V1 may use a shared Marketing Operations engine with an Agent 23 profile. Deterministic stages include required-field validation, missing trigger/audience checks, forbidden-action detection, suppression/exit completeness checks, QA coverage checks, and status mapping. LLM-assisted stages synthesize the workflow map, branch rationale, monitoring notes, and implementation-readable wording from supplied context.

## 5. State Model

Request-scoped state should contain:

- normalized workflow brief and upstream handoffs
- trigger, entry criteria, audience criteria, and consent/suppression constraints
- workflow steps, branch logic, wait/cadence steps, and exit criteria
- asset/content requirements and field/data dependencies
- QA test cases
- rollback and monitoring notes
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain MAP, CRM, email/SMS, webhook, contact-list, consent-database, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- workflow objective, campaign/nurture goal, trigger/entry event, target audience, offer/content sequence
- suppression, consent, exclusion, regional, lifecycle, and routing constraints
- field and data dependencies, asset inventory, cadence preferences, wait-step rules, exit criteria
- Agents 13, 19, 22, 26, and 27 handoffs
- QA expectations, rollback considerations, monitoring goals, assumptions, and source labels

## 7. Outputs

Primary output concepts:

- `MarketingAutomationWorkflowDesignPackage`
- `WorkflowMap`
- `EntryCriteria`
- `BranchRule`
- `WaitStep`
- `SuppressionRule`
- `ExitCriteria`
- `AssetRequirement`
- `FieldDependency`
- `WorkflowQATestCase`
- `RollbackMonitoringNote`
- `MarketingOperationsHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `MarketingAutomationWorkflowDesignRequest`
- `WorkflowObjective`
- `WorkflowStep`
- `WorkflowBranch`
- `SuppressionExclusionRule`
- `WorkflowExitRule`
- `WorkflowDataDependency`
- `WorkflowQACase`
- `WorkflowDesignQualityReport`
- `MarketingAutomationWorkflowDesignPackage`

Shared status, risk, evidence, assumption, cost, readiness, and handoff contracts should be reused if `packages/marketing_operations` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_workflow_inputs` | request | missing trigger/audience/goal/consent blockers | None | Local only |
| `detect_workflow_forbidden_actions` | request text | activation/send/import/update hard-fail flags | None | Local only |
| `check_suppression_exit_coverage` | workflow draft | suppression/exit warnings | None | Local only |
| `check_data_dependency_gaps` | fields/assets/context | data and asset gaps | None | Local only |
| `score_workflow_design` | workflow, QA cases, risks | quality report | None | Local only |
| `build_agent28_handoff` | final package | structured launch-readiness handoff | None | Local only |

No MAP, CRM, email, SMS, webhook, API execution, list upload, consent database, or workflow activation tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent workflow memory in v1.
- Prior workflow examples can be supplied directly by the user as untrusted context.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require workflow objective, trigger/entry event, audience criteria, and consent/suppression context.
- Missing trigger or unclear audience returns `needs_human`.
- Missing assets, data fields, exit criteria, rollback notes, or monitoring goals should be warnings unless they block safe implementation.
- Hard-flag requests to create/activate workflows, send messages, import contacts, update lists, update CRM, execute webhooks/APIs, or bypass consent/suppression.
- Preserve upstream consent and routing constraints in the final workflow design.
- Recommendations must cite supplied strategy, handoffs, or assumptions.

## 12. Prompt Strategy

- User-provided notes, campaign briefs, CRM/MAP exports, field lists, routing rules, tracking plans, compliance notes, and launch checklists are untrusted.
- Untrusted text must be fenced and delimiter-escaped.
- User-supplied data must never override system/developer instructions.
- The model must not invent system access, approvals, consent, legal certification, data quality results, launch status, or live-system changes.
- All recommendations must cite supplied evidence or be labeled as assumptions/heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

Agent 23 prompts should ask for implementation-readable workflow specifications while explicitly stating that the output is not a MAP export, API payload, activated workflow, or send authorization.

## 13. Quality Scoring Strategy

Agent 23 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Trigger and audience clarity | 20 |
| Branch and step logic completeness | 15 |
| Cadence, suppression, and exit quality | 20 |
| Asset and data dependency coverage | 15 |
| QA test case usefulness | 15 |
| Rollback and monitoring readiness | 5 |
| Scope, consent, and activation safety | 10 |

Pass if score >= 84 and no hard-fail risk. Hard-fail risks override the numeric score.

## 14. Evaluation Strategy

Eval datasets should cover complete nurture workflow, campaign workflow with routing constraints, missing trigger, unclear audience, missing suppression, missing exit, send/activate/import request, consent bypass, webhook execution request, and prompt injection.

CI gates:

- schema_valid = 100%
- missing_trigger_behavior = 100%
- no_send_activate_import_behavior = 100%
- consent_suppression_safety = 100%
- workflow_section_coverage >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 15. Error Handling Strategy

- Missing trigger or audience criteria returns `needs_human`.
- Activation, send, import, list-update, webhook, API execution, or consent-bypass requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with deterministic validation and safe partial workflow outline if available.
- Provider failure returns `error` with redacted category and preserved cost usage.
- Conflicting routing/consent inputs return `needs_human` with reconciliation questions.

## 16. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, validation, workflow design, suppression/exit checks, QA case generation, risk detection, scoring, finalization
- token/cost by stage
- trigger count, branch count, wait-step count, suppression rule count, exit rule count, QA case count, dependency gap count, quality score, risk counts
- no raw contact records, email addresses, phone numbers, consent lists, suppression lists, workflow exports, or full campaign notes in logs

## 17. Cloud Agnostic Review

- No cloud SDK imports inside `agent/`.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No MAP, CRM, email/SMS, webhook/API, contact-list, consent database, direct model SDK, or `litellm` imports inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents.
- Bedrock/Azure must remain config/stub compatible.
- Shared `packages/marketing_operations` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render workflow maps, trigger/branch trees, wait steps, suppression/exclusion rules, exit criteria, field dependencies, QA cases, rollback notes, monitoring notes, risk flags, and Agent 28 handoff. Studio may later support MAP export or implementation tickets only after separate provider-neutral write designs and human approval gates.

## 19. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine with an Agent 23 profile. The profile should define workflow output sections, trigger/audience validation, suppression/exit checks, activation/send/import hard-fails, QA case requirements, quality dimensions, and eval cases. Future versions may add provider-neutral MAP read/write connectors, but live workflow activation remains out of v1.
