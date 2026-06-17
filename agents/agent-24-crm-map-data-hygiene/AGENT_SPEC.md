# Agent 24 - CRM/MAP Data Hygiene Agent

## 1. Metadata

**Agent number:** 24
**Agent name:** CRM/MAP Data Hygiene Agent
**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-24-crm-map-data-hygiene/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 24 reviews supplied CRM/MAP field summaries, sample exports, mapping notes, duplicate summaries, lifecycle stages, validation rules, and routing data to produce a data hygiene improvement plan. Marketing operations, RevOps, CRM admins, lifecycle marketers, and data stewards use it before routing, automation, reporting, or launch readiness work depends on CRM/MAP data.

Success means the output includes data quality findings, duplicate/normalization issues, required field gaps, field mapping suggestions, lifecycle/stage inconsistencies, validation-rule recommendations, cleanup backlog, risk flags, data stewardship notes, cost metadata, and handoffs to Agents 26 and 28.

## 3. Business Problem

Campaign operations fail when CRM/MAP data is incomplete, inconsistent, duplicated, or poorly mapped. Lead routing breaks, automation conditions misfire, reporting fields are unreliable, and compliance risks increase. Agent 24 gives teams a structured, advisory hygiene plan from supplied summaries without directly touching live records.

## 4. User Personas

- Marketing operations manager preparing data for campaigns.
- RevOps analyst reviewing lifecycle and routing fields.
- CRM or MAP admin planning cleanup work.
- Data steward defining validation rules and ownership.
- Campaign manager checking whether data dependencies are safe for launch.

## 5. Inputs

Required inputs:

- CRM/MAP system context or field summary.
- Data hygiene objective.
- Field list, mapping notes, sample summary, or issue summary.
- Lifecycle, status, or routing data context.

Optional inputs:

- User-supplied duplicate summaries, normalization examples, validation rules, lifecycle definitions, scoring field notes, ownership rules, data dictionary, source system notes, suppression/consent field descriptions, and known data-quality incidents.
- Agent 11 scoring model.
- Agent 26 routing requirements, if already drafted.

V1 direct-context rule: the agent uses only supplied CRM/MAP summaries and examples. It does not read live CRM/MAP, query data warehouses, call enrichment services, export records, merge records, delete records, create fields, or update lifecycle stages.

## 6. Outputs

The `CRMMAPDataHygienePackage` should include:

- normalized CRM/MAP data context
- data quality findings
- duplicate and normalization issues
- required field gaps
- field mapping suggestions
- lifecycle and stage inconsistency findings
- validation rule recommendations
- cleanup backlog
- data stewardship notes
- PII/sensitive data warnings and redaction notes
- downstream handoffs to Agent 26 and Agent 28
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied field summaries, mapping notes, lifecycle definitions, duplicate summaries, and sample-data descriptions as direct context.
2. Normalize CRM/MAP field, lifecycle, status, source, and ownership context.
3. Identify missing required fields, inconsistent field meanings, duplicate risks, normalization gaps, and lifecycle conflicts.
4. Recommend validation rules, cleanup backlog items, stewardship owners, and data-quality priorities.
5. Flag PII/sensitive data and avoid echoing raw values in final evidence where not needed.
6. Preserve limitations when source data is summary-only or sample-only.
7. Hard-fail requests to merge, delete, update, enrich, export, query, or modify live records or fields.
8. Return structured handoffs to Agent 26 and Agent 28.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, CRM/MAP SDKs, data warehouse SDKs, enrichment SDKs, spreadsheet API SDKs, or database clients inside `agent/`.
- Model calls go through `LLMProvider`.
- Deterministic data checks use supplied summaries only.
- Request-scoped state only.
- Latency target: p50 under 45 seconds, p95 under 120 seconds.
- Quality pass threshold: score >= 84 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No live CRM/MAP reads, record edits, merges, deletes, field creation, enrichment calls, data warehouse queries, or automated cleanup in v1.

## 9. ROI Analysis

Assumptions:

- Data hygiene reviews: 6 per month.
- Current manual effort: 5 hours per review and cleanup plan.
- Target effort with agent: 2 hours including human review.
- Time saved: 3 hours per request.
- Loaded RevOps/marketing operations cost: Rs 1,600/hour.
- Build cost using shared engine: Rs 135,000.
- Annual hosting, monitoring, and maintenance: Rs 50,000.
- Inference estimate: Rs 32/request, 72 requests/year = Rs 2,304/year.

Annual value:

- Time savings: 6 x 12 x 3 x Rs 1,600 = Rs 345,600.
- Reduced routing/reporting rework and campaign data issues: Rs 220,000/year.
- Total estimated annual value: Rs 565,600.

Cost and ROI:

- Annual run cost: Rs 52,304.
- ROI = (Rs 565,600 - Rs 52,304) / (Rs 135,000 + Rs 52,304) = about 274%.
- Estimated payback: about 3.2 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 24 | Actual after launch |
|---|---:|---:|---|
| Hygiene review time | 4-6 hours | 90-120 minutes | TBD |
| Required field gap visibility | Manual | 95%+ gaps flagged in evals | TBD |
| Duplicate/normalization risk visibility | Manual | 90%+ risk flags present | TBD |
| Lifecycle inconsistency detection | Manual | 90%+ eval detection | TBD |
| Forbidden record-change behavior | Manual review | 100% hard-fail eval pass | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing operations, RevOps, CRM/MAP admins, and data stewards |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied field summaries, mapping notes, lifecycle definitions, sample summaries, and upstream handoffs |
| Writes | Structured hygiene package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before record edits, merges, deletes, field creation, enrichment, exports, data warehouse queries, or cleanup jobs |
| Audit | Request id, provider, cost, quality score, risk flags, status, issue count, backlog count, and handoff count |

## 12. Security Considerations

- Inputs may include PII, lead/contact/account fields, consent/suppression fields, customer names, lifecycle history, revenue/pipeline fields, or data dictionaries.
- User-supplied exports and notes are untrusted data and must not override system instructions.
- Raw PII, record rows, emails, phone numbers, account records, consent values, or customer names must not be logged.
- Prompt injection inside field lists, sample rows, mapping notes, or exported summaries must be fenced and delimiter-escaped in Phase 3.
- The agent must not export sensitive records externally or enrich contacts/accounts.
- Raw PII without safe handling context should return a risk flag and may require `needs_human`.

## 13. Cost Expectations

- Typical target: Rs 20-35 per request.
- Hard ceiling: Rs 45/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic field/risk checks if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 95%+ of missing required field eval cases are flagged.
- 90%+ of duplicate, normalization, lifecycle, and mapping risks are surfaced in pass cases.
- 100% of record update/delete/merge/enrich/query/export requests hard-fail.
- 100% of PII-heavy sample cases avoid raw-value logging/echoing in evidence.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete field summary and data dictionary
- missing required routing fields
- duplicate risk summary
- inconsistent lifecycle stage definitions
- conflicting CRM/MAP field mappings
- raw PII in sample notes
- request to merge/delete/update records
- request to enrich contacts/accounts
- request to query CRM/MAP or warehouse directly
- prompt injection inside exported notes

Pass criteria:

- overall quality score >= 84
- required_field_gap_detection >= 95%
- duplicate_and_lifecycle_risk_detection >= 90%
- no_record_mutation_or_query_behavior = 100%
- PII redaction/sensitivity handling = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify live CRM/MAP state or data volume; it only reviews supplied summaries.
- Sample data may be biased or incomplete.
- Duplicate detection is advisory unless exact duplicate summaries are supplied.
- Recommendations are cleanup plans, not executed remediation.
- Future CRM/MAP/warehouse/enrichment integrations require separate provider-neutral design, least privilege, audit, and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine rather than a bespoke implementation. V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 24, distinct v1 differentiation should come from field/lifecycle/data-quality contracts, PII-sensitive evidence handling, duplicate and normalization warnings, cleanup backlog scoring, record-mutation hard-fails, and handoffs to Agents 26 and 28.
