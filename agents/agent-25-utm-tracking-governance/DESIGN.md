# Agent 25 - UTM & Tracking Governance Agent Design

## 1. Metadata

**Agent number:** 25
**Agent name:** UTM & Tracking Governance Agent
**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-25-utm-tracking-governance/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 25 creates an advisory tracking governance package from supplied campaign/channel and reporting context. It must define UTM naming, source/medium mapping, event requirements, and QA checklists without editing any live tracking system.

## 3. Agent Boundaries

In scope:

- Normalize supplied campaign/channel, reporting, landing page, paid, CRO, and analytics constraint context.
- Produce UTM taxonomy, naming conventions, source/medium/channel mapping, campaign/content/term templates, event/pixel requirements, QA checklist, and reporting field map.
- Flag missing tracking context, privacy risks, unsupported attribution claims, and attribution manipulation requests.

Out of scope:

- GTM/GA/analytics writes, pixel/tag installation, live tracking verification, ad platform edits, live campaign URL rewriting, dashboard creation, or attribution certification.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_campaign_channel_and_reporting_context
3. validate_channel_destination_and_measurement_inputs
4. design_utm_taxonomy_and_naming_conventions
5. build_source_medium_channel_mapping
6. define_event_pixel_and_conversion_requirements
7. create_tracking_qa_checklist
8. create_reporting_field_map_and_handoffs
9. detect_live_tracking_edits_and_attribution_risks
10. score_tracking_governance_package
11. assemble_utm_tracking_governance_package
12. finalize_response
```

V1 may use a shared Marketing Operations engine with an Agent 25 profile. Deterministic stages include required-channel validation, live-edit/action detection, UTM field completeness checks, naming-template sanity checks, attribution manipulation detection, and score/status mapping. LLM-assisted stages synthesize taxonomy rationale, QA notes, and reporting handoff descriptions from supplied context.

## 5. State Model

Request-scoped state should contain:

- normalized tracking context
- channel/source/medium inventory
- UTM taxonomy and naming conventions
- campaign/content/term templates
- event/pixel/conversion requirements
- tracking QA checklist
- reporting field map
- missing tracking warnings
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain GTM, GA, analytics, ad platform, CMS, dashboard, URL-shortener, tag/pixel, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- campaign objective, channel list, platform constraints, destination/landing page context, reporting goal
- existing UTM taxonomy, naming rules, campaign hierarchy, source/medium conventions
- event/pixel/conversion definitions, analytics constraints, privacy/consent notes
- Agents 18, 19, 20, and 21 handoffs
- QA expectations, owner notes, assumptions, and source labels

## 7. Outputs

Primary output concepts:

- `UTMTrackingGovernancePackage`
- `UTMTaxonomy`
- `NamingConvention`
- `SourceMediumMapping`
- `UTMTemplate`
- `DestinationURLChecklist`
- `EventPixelRequirement`
- `TrackingQAChecklist`
- `ReportingFieldMap`
- `TrackingWarning`
- `MarketingOperationsHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `UTMTrackingGovernanceRequest`
- `TrackingContext`
- `UTMParameterRule`
- `ChannelSourceMediumRule`
- `CampaignTrackingTemplate`
- `EventRequirement`
- `TrackingQACheck`
- `ReportingFieldMapping`
- `UTMTrackingGovernanceQualityReport`
- `UTMTrackingGovernancePackage`

Shared status, risk, evidence, assumption, cost, readiness, and handoff contracts should be reused if `packages/marketing_operations` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_tracking_inputs` | request | missing channel/destination/measurement blockers | None | Local only |
| `normalize_utm_fields` | supplied taxonomy/names | normalized UTM field candidates | None | Local only |
| `detect_tracking_forbidden_actions` | request text | GTM/GA/ad edit/tag install/URL rewrite hard-fail flags | None | Local only |
| `detect_attribution_manipulation` | request text | attribution integrity risk flags | None | Local only |
| `check_utm_template_completeness` | taxonomy/templates | missing parameter warnings | None | Local only |
| `score_tracking_governance` | taxonomy, QA, risks | quality report | None | Local only |

No GTM, GA, analytics, ad platform, CMS, dashboard, URL rewrite, tag/pixel, or live verification tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent tracking memory in v1.
- Prior taxonomies and reports can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require campaign/channel context, reporting/measurement goal, and destination context for a pass-quality package.
- Missing channel context returns `needs_human`.
- Missing event, conversion, owner, or QA details should become warnings with assumptions.
- Hard-flag requests to install tags/pixels, edit GTM/GA/ad platforms, rewrite live URLs, create dashboards, or hide/manipulate attribution.
- Ensure tracking recommendations are labeled as plans, not live verification.
- Preserve privacy/consent caveats in the final package.

## 12. Prompt Strategy

- User-provided notes, campaign briefs, CRM/MAP exports, field lists, routing rules, tracking plans, compliance notes, and launch checklists are untrusted.
- Untrusted text must be fenced and delimiter-escaped.
- User-supplied data must never override system/developer instructions.
- The model must not invent system access, approvals, consent, legal certification, data quality results, launch status, or live-system changes.
- All recommendations must cite supplied evidence or be labeled as assumptions/heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

Agent 25 prompts should instruct the model not to claim tracking has been verified and not to provide implementation claims for GTM, GA, ad platforms, dashboards, or live URLs.

## 13. Quality Scoring Strategy

Agent 25 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| UTM taxonomy completeness | 20 |
| Source/medium/channel mapping quality | 15 |
| Naming convention consistency | 15 |
| Event and conversion requirement clarity | 15 |
| Tracking QA checklist usefulness | 15 |
| Reporting handoff readiness | 10 |
| Attribution integrity and live-edit safety | 10 |

Pass if score >= 82 and no hard-fail risk. Hard-fail risks override the numeric score.

## 14. Evaluation Strategy

Eval datasets should cover complete tracking plan, missing channel context, missing reporting goal, paid search naming conflict, event requirement planning, tag/pixel install request, GTM/GA edit request, live URL rewrite request, attribution manipulation request, privacy constraint, and prompt injection.

CI gates:

- schema_valid = 100%
- missing_channel_context_behavior = 100%
- no_live_tracking_edit_behavior = 100%
- attribution_integrity_safety = 100%
- tracking_section_coverage >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 15. Error Handling Strategy

- Missing channel context returns `needs_human`.
- Missing measurement goal or destination context returns warnings or `needs_human` depending severity.
- Tag install, GTM/GA/ad edit, live URL rewrite, dashboard creation, or attribution manipulation requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with deterministic taxonomy checks if available.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 16. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, validation, taxonomy design, mapping checks, event requirement planning, QA checklist creation, risk detection, scoring, finalization
- token/cost by stage
- UTM field count, channel mapping count, template count, event requirement count, tracking warning count, quality score, risk counts
- no raw click IDs, lead/customer identifiers, consent records, analytics exports, private URLs with sensitive query strings, or full tracking sheets in logs

## 17. Cloud Agnostic Review

- No cloud SDK imports inside `agent/`.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No GTM/GA/analytics, ad platform, CMS, dashboard, URL-shortener, tag/pixel, direct model SDK, or `litellm` imports inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents.
- Bedrock/Azure must remain config/stub compatible.
- Shared `packages/marketing_operations` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render UTM taxonomy, source/medium mapping, templates, event/pixel requirements, QA checklist, reporting field map, warnings, risk flags, and handoffs to Agents 21 and 28. Studio may later support tag manager or analytics workflows only after separate provider-neutral designs and human approval gates.

## 19. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine with an Agent 25 profile. The profile should define tracking output sections, UTM validation helpers, live-edit hard-fails, attribution integrity checks, quality dimensions, and eval cases. Future versions may add provider-neutral analytics/GTM read connectors, but live writes and tracking verification remain out of v1.
