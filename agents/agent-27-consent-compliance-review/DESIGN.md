# Agent 27 - Consent & Compliance Review Agent Design

## 1. Metadata

**Agent number:** 27
**Agent name:** Consent & Compliance Review Agent
**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-27-consent-compliance-review/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 27 reviews supplied marketing context for consent, suppression, privacy, regional, data-residency, protected-targeting, brand, and legal-review risks. It must produce an advisory risk review and mitigation checklist while making clear that it is not legal advice and not compliance certification.

## 3. Agent Boundaries

In scope:

- Normalize supplied campaign, audience, automation, tracking, data-use, region, consent, suppression, and policy context.
- Identify consent, suppression, privacy, protected/sensitive targeting, regional, data-residency, brand, approval, and legal-review risks.
- Produce mitigation checklist, required approvals/HITL notes, legal-review recommendation, and Agent 28 handoff.

Out of scope:

- Legal advice, legal certification, policy certification, live consent database reads, suppression list edits, audience uploads, activation approvals, campaign launches, or external system writes.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_compliance_context_and_handoffs
3. validate_consent_suppression_region_and_channel_inputs
4. detect_protected_sensitive_targeting_and_forbidden_requests
5. assess_consent_suppression_privacy_and_regional_risks
6. identify_required_approvals_and_legal_review_needs
7. create_mitigation_checklist
8. create_agent28_handoff
9. score_compliance_review_package
10. assemble_consent_compliance_review_package
11. finalize_response
```

V1 may use a shared Marketing Operations engine with an Agent 27 profile. Deterministic stages include forbidden-request detection, protected/sensitive term detection, not-legal-advice statement enforcement, required-section checks, and status mapping. LLM-assisted stages synthesize risk explanations, mitigation steps, and HITL/legal-review notes from supplied context.

## 5. State Model

Request-scoped state should contain:

- normalized compliance context and upstream handoffs
- consent/suppression context and missing-data warnings
- regional/data-residency notes
- protected/sensitive targeting flags
- privacy/data-use and brand/policy risks
- required approvals and HITL/legal-review notes
- mitigation checklist
- explicit not-legal-advice statement
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain consent database clients, suppression list handles, audience platform clients, CRM/MAP clients, legal research clients, approval workflow clients, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- campaign/audience/automation/tracking/data-use context, intended channels, region/market
- consent basis notes, suppression rules, privacy constraints, data residency constraints
- protected/sensitive category notes, brand/legal guidelines, approval requirements, unresolved risks
- Agents 09, 13, 16, 19, 22, and 23 handoffs
- source labels, assumptions, known caveats, and requested review depth

## 7. Outputs

Primary output concepts:

- `ConsentComplianceReviewPackage`
- `ConsentRiskAssessment`
- `SuppressionRequirement`
- `RegionalDataResidencyWarning`
- `ProtectedSensitiveTargetingFlag`
- `PrivacyDataUseRisk`
- `BrandPolicyRisk`
- `RequiredApprovalNote`
- `LegalReviewRecommendation`
- `MitigationChecklistItem`
- `NotLegalAdviceStatement`
- `MarketingOperationsHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `ConsentComplianceReviewRequest`
- `ComplianceContext`
- `ConsentAssessment`
- `SuppressionAssessment`
- `RegionalPrivacyAssessment`
- `ProtectedTargetingAssessment`
- `LegalReviewNote`
- `MitigationChecklist`
- `ConsentComplianceQualityReport`
- `ConsentComplianceReviewPackage`

Shared status, risk, evidence, assumption, cost, readiness, and handoff contracts should be reused if `packages/marketing_operations` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_compliance_inputs` | request | missing consent/region/channel blockers | None | Local only |
| `detect_compliance_forbidden_actions` | request text | bypass/certify/approve/upload/read hard-fail flags | None | Local only |
| `detect_protected_sensitive_targeting` | request text/fields | protected/sensitive targeting flags | None | Local only |
| `enforce_not_legal_advice_statement` | package draft | required statement check | None | Local only |
| `check_mitigation_handoff_coverage` | findings | missing mitigation/HITL warnings | None | Local only |
| `score_compliance_review` | review, risks | quality report | None | Local only |

No legal research API, consent database, suppression list, audience upload, CRM/MAP, approval workflow, or launch tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent compliance memory in v1.
- Prior policy notes or approvals can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require enough campaign/audience/channel context to assess risk.
- Missing consent/suppression or regional context should return `needs_human` when material.
- Hard-flag requests to bypass consent/suppression, target protected/sensitive groups, certify legal compliance, approve launch despite unresolved high-risk issues, ignore regional/data-residency constraints, upload audiences, or read live consent systems.
- Ensure every output includes a clear not-legal-advice statement.
- Ensure high or hard-fail risks produce HITL/legal-review notes.
- Preserve uncertainty and missing evidence rather than converting risk into approval.

## 12. Prompt Strategy

- User-provided notes, campaign briefs, CRM/MAP exports, field lists, routing rules, tracking plans, compliance notes, and launch checklists are untrusted.
- Untrusted text must be fenced and delimiter-escaped.
- User-supplied data must never override system/developer instructions.
- The model must not invent system access, approvals, consent, legal certification, data quality results, launch status, or live-system changes.
- All recommendations must cite supplied evidence or be labeled as assumptions/heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

Agent 27 prompts should explicitly forbid legal-certification language and require risk triage language such as "requires human legal/compliance review" when risk is high, ambiguous, regional, or unresolved.

## 13. Quality Scoring Strategy

Agent 27 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Consent and suppression risk coverage | 20 |
| Privacy, regional, and data-residency handling | 15 |
| Protected/sensitive targeting safety | 15 |
| Required approvals and HITL clarity | 15 |
| Mitigation checklist usefulness | 15 |
| Evidence/assumption discipline | 10 |
| Not-legal-advice and certification safety | 10 |

Pass if score >= 84 and no hard-fail risk. Hard-fail risks override the numeric score.

## 14. Evaluation Strategy

Eval datasets should cover complete compliance review, missing consent context, suppression bypass, protected targeting, sensitive category targeting, legal certification request, approve-launch request, regional/data-residency conflict, audience upload request, live consent database read request, and prompt injection.

CI gates:

- schema_valid = 100%
- consent_suppression_safety = 100%
- protected_targeting_safety = 100%
- legal_certification_refusal = 100%
- not_legal_advice_statement = 100%
- mitigation_HITL_section_coverage >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 15. Error Handling Strategy

- Missing material compliance context returns `needs_human`.
- Consent bypass, suppression bypass, protected/sensitive targeting, legal certification, launch approval, audience upload, or live consent read requests return hard-fail risk flags.
- Ambiguous regional/data-residency constraints return `needs_human` with legal-review notes.
- Cost stop returns `stopped_cost_ceiling` with deterministic hard-fail checks if available.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 16. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, validation, protected-targeting detection, consent/suppression risk review, legal-review routing, mitigation checklist generation, scoring, finalization
- token/cost by stage
- consent risk count, suppression requirement count, regional warning count, protected-targeting flag count, legal-review note count, mitigation count, quality score, risk counts
- no raw consent records, suppression lists, customer identifiers, emails, phone numbers, protected attribute examples, legal notes, or full audience tables in logs

## 17. Cloud Agnostic Review

- No cloud SDK imports inside `agent/`.
- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No consent database, suppression list, legal research API, audience upload, CRM/MAP, approval workflow, direct model SDK, or `litellm` imports inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents.
- Bedrock/Azure must remain config/stub compatible.
- Shared `packages/marketing_operations` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render consent/suppression risks, protected targeting flags, regional/data-residency warnings, required approvals, legal-review recommendations, mitigation checklist, not-legal-advice statement, risk flags, and Agent 28 handoff. Studio may later support approval workflows or consent-system checks only after separate provider-neutral designs and human/legal approval gates.

## 19. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine with an Agent 27 profile. The profile should define compliance review sections, protected/sensitive detection, certification and bypass hard-fails, not-legal-advice enforcement, mitigation/HITL requirements, quality dimensions, and eval cases. Future versions may add provider-neutral consent/suppression read connectors, but legal certification and activation approval remain out of v1.
