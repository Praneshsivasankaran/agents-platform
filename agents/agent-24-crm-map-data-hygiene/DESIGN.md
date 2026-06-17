# Agent 24 - CRM/MAP Data Hygiene Agent Design

## 1. Metadata

**Agent number:** 24
**Agent name:** CRM/MAP Data Hygiene Agent
**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-24-crm-map-data-hygiene/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 24 reviews supplied CRM/MAP data summaries and produces an advisory data hygiene plan. It must identify field, mapping, duplicate, lifecycle, validation, ownership, and PII/sensitive-data risks without reading or modifying live records.

## 3. Agent Boundaries

In scope:

- Normalize supplied field summaries, mapping notes, lifecycle definitions, duplicate summaries, validation rules, and issue notes.
- Identify missing required fields, field mapping inconsistencies, duplicate/normalization risks, lifecycle/stage conflicts, and cleanup backlog items.
- Recommend validation rules, stewardship notes, and handoffs to routing and launch-readiness work.

Out of scope:

- Live CRM/MAP reads, record edits, record merges/deletes, field creation, enrichment calls, data warehouse queries, external exports, automated cleanup, or live data-quality certification.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_data_context_and_handoffs
3. detect_pii_sensitive_data_and_forbidden_actions
4. validate_field_summary_and_mapping_context
5. identify_required_field_gaps
6. identify_duplicate_normalization_and_lifecycle_issues
7. recommend_validation_rules_and_cleanup_backlog
8. create_stewardship_and_handoff_notes
9. score_data_hygiene_package
10. assemble_crm_map_data_hygiene_package
11. finalize_response
```

V1 may use a shared Marketing Operations engine with an Agent 24 profile. Deterministic stages include required-field validation, forbidden mutation/query detection, coarse PII detection/redaction, duplicate/lifecycle issue classification from supplied summaries, and score/status mapping. LLM-assisted stages synthesize cleanup recommendations, stewardship notes, and prioritization rationale from supplied evidence.

## 5. State Model

Request-scoped state should contain:

- normalized CRM/MAP context
- field inventory and mapping notes
- lifecycle/stage definitions
- duplicate and normalization findings
- required field gaps
- validation rule recommendations
- cleanup backlog and stewardship notes
- PII/sensitive-data warnings and redaction notes
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain CRM/MAP clients, database connections, warehouse clients, enrichment clients, spreadsheet API clients, exported record handles, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- CRM/MAP system context, field list, data dictionary, field mapping notes, lifecycle/status definitions
- supplied sample summaries, duplicate summaries, normalization examples, data-quality issue notes
- scoring field notes, routing requirements, consent/suppression field descriptions, ownership rules
- Agent 11 scoring model and Agent 26 routing requirements if supplied
- source labels, confidence notes, assumptions, and data handling constraints

## 7. Outputs

Primary output concepts:

- `CRMMAPDataHygienePackage`
- `DataQualityFinding`
- `FieldGap`
- `FieldMappingSuggestion`
- `DuplicateNormalizationIssue`
- `LifecycleStageInconsistency`
- `ValidationRuleRecommendation`
- `CleanupBacklogItem`
- `DataStewardshipNote`
- `PIISensitivityWarning`
- `MarketingOperationsHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `CRMMAPDataHygieneRequest`
- `CRMFieldSummary`
- `FieldMappingAssessment`
- `LifecycleStageDefinition`
- `DuplicateRiskSummary`
- `DataQualityFinding`
- `ValidationRule`
- `CleanupBacklogItem`
- `CRMMAPDataHygieneQualityReport`
- `CRMMAPDataHygienePackage`

Shared status, risk, evidence, assumption, cost, readiness, and handoff contracts should be reused if `packages/marketing_operations` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `detect_pii_and_sensitive_fields` | supplied text/field labels | PII/sensitive warnings and redaction notes | None | Local only |
| `detect_data_hygiene_forbidden_actions` | request text | mutation/query/export/enrichment hard-fail flags | None | Local only |
| `validate_field_summary_context` | request | missing field/mapping/lifecycle blockers | None | Local only |
| `detect_required_field_gaps` | field summary and routing context | required field gaps | None | Local only |
| `detect_lifecycle_mapping_issues` | lifecycle and mapping notes | inconsistency warnings | None | Local only |
| `score_data_hygiene_package` | findings, backlog, risks | quality report | None | Local only |

No CRM, MAP, database, warehouse, enrichment, spreadsheet API, record export, or cleanup execution tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent CRM/MAP memory in v1.
- Prior data dictionaries or cleanup notes can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require CRM/MAP context, data hygiene objective, and at least one field summary, mapping note, sample summary, or issue summary.
- Missing core data context returns `needs_human`.
- Raw PII or record-level examples should be flagged, redacted/summarized in evidence, and may require human handling.
- Hard-flag requests to update, merge, delete, enrich, export, query, or create fields/records.
- Mark all data-quality conclusions as based on supplied summaries only.
- Ensure recommendations include owner/stewardship and cleanup-priority context.

## 12. Prompt Strategy

- User-provided notes, campaign briefs, CRM/MAP exports, field lists, routing rules, tracking plans, compliance notes, and launch checklists are untrusted.
- Untrusted text must be fenced and delimiter-escaped.
- User-supplied data must never override system/developer instructions.
- The model must not invent system access, approvals, consent, legal certification, data quality results, launch status, or live-system changes.
- All recommendations must cite supplied evidence or be labeled as assumptions/heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

Agent 24 prompts should ask the model to avoid echoing raw PII, to describe evidence at summary level, and to distinguish cleanup recommendations from executed cleanup.

## 13. Quality Scoring Strategy

Agent 24 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Field and mapping assessment quality | 20 |
| Required field and validation gap detection | 15 |
| Duplicate and normalization issue handling | 15 |
| Lifecycle/stage inconsistency handling | 15 |
| Cleanup backlog actionability | 15 |
| PII/sensitive-data handling | 10 |
| Scope and live-system safety | 10 |

Pass if score >= 84 and no hard-fail risk. Hard-fail risks override the numeric score.

## 14. Evaluation Strategy

Eval datasets should cover complete field summary, missing required routing fields, conflicting field mappings, duplicate risk summary, lifecycle inconsistency, raw PII sample notes, record update/delete/merge requests, enrichment request, live CRM/MAP query request, export request, and prompt injection.

CI gates:

- schema_valid = 100%
- required_field_gap_detection >= 95%
- duplicate_lifecycle_mapping_detection >= 90%
- no_record_mutation_query_export_behavior = 100%
- PII_sensitive_handling = 100%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 15. Error Handling Strategy

- Missing CRM/MAP context or field/issue summary returns `needs_human`.
- Raw PII-heavy input returns PII risk flags and may return `needs_human`.
- Mutation, merge, delete, enrichment, export, query, or field-creation requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with deterministic findings if available.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 16. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, PII detection, validation, field-gap detection, lifecycle/mapping checks, cleanup backlog generation, scoring, finalization
- token/cost by stage
- field issue count, required gap count, duplicate warning count, lifecycle inconsistency count, validation recommendation count, cleanup backlog count, quality score, risk counts
- no raw record rows, emails, phone numbers, customer/account names, consent values, revenue fields, exported data, or full field notes in logs

## 17. Cloud Agnostic Review

- No cloud SDK imports inside `agent/`.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No CRM/MAP, database, warehouse, enrichment, spreadsheet API, direct model SDK, or `litellm` imports inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents.
- Bedrock/Azure must remain config/stub compatible.
- Shared `packages/marketing_operations` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render data quality findings, field gaps, mapping suggestions, lifecycle issues, duplicate/normalization warnings, cleanup backlog items, stewardship owners, PII/sensitivity warnings, and handoffs to Agents 26 and 28. Studio may later integrate with CRM/MAP data catalogs or cleanup systems only after separate provider-neutral read/write designs and human approval gates.

## 19. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine with an Agent 24 profile. The profile should define field/mapping/lifecycle output sections, PII-sensitive handling, mutation/query/export hard-fails, cleanup backlog scoring, quality dimensions, and eval cases. Future versions may add provider-neutral CRM/MAP read connectors or deterministic duplicate calculators, but live cleanup remains out of v1.
