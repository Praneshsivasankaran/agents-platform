# Agent 16 - Ad Copy Creation Agent Design

## 1. Metadata

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-16-ad-copy-creation/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 16 creates safe, review-ready ad copy variants and message briefs from supplied campaign context. It must help teams move faster without crossing into activation, policy bypass, unsupported claims, or protected targeting.

## 3. Agent Boundaries

In scope:

- Draft search, social, display, or native ad copy variants.
- Generate headlines, descriptions, CTAs, message angles, and A/B test ideas.
- Map claims to supplied evidence.
- Flag compliance, policy, and platform-fit risks.

Out of scope:

- Publishing, launching, uploading, approving, pausing, or editing ads.
- Audience upload or targeting execution.
- Spend, budget changes, bid changes, or live platform reads.
- Unsupported regulated claims, deceptive urgency, or policy-bypass guidance.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_campaign_context
3. validate_offer_audience_platform_inputs
4. inventory_claims_and_evidence
5. detect_policy_and_activation_risks
6. generate_message_angles
7. draft_platform_variants
8. validate_copy_constraints_and_claims
9. generate_ab_test_ideas
10. score_ad_copy_package
11. assemble_ad_copy_creation_package
12. finalize_response
```

Deterministic stages include required-field validation, forbidden-action detection, protected-targeting checks, claim-evidence inventory, simple character-count checks where limits are supplied, and status mapping. LLM-assisted stages include message angle creation, variant drafting, and rationale writing.

## 5. State Model

Request-scoped state should contain:

- normalized campaign and audience context
- platform and format requirements
- keyword and offer context
- claim evidence inventory
- policy/compliance risk flags
- message angles
- ad copy variants
- A/B test ideas
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain ad platform clients, provider SDK objects, or raw provider responses.

## 6. Inputs

Primary input concepts:

- campaign goal, offer, product/service, audience/segment
- platform targets and format constraints
- keyword clusters from Agent 15
- campaign recommendation or lead generation blueprint from Agents 10/12
- brand voice, proof points, claims evidence, compliance restrictions
- examples to emulate or avoid, treated as untrusted direct context

## 7. Outputs

Primary output concepts:

- `AdCopyCreationPackage`
- `AdVariant`
- `HeadlineSet`
- `DescriptionSet`
- `CTAOption`
- `MessageAngle`
- `ClaimEvidenceMap`
- `PlatformFitNote`
- `ComplianceWarning`
- `ABTestIdea`
- `DigitalMarketingHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `AdCopyCreationRequest`
- `PlatformConstraint`
- `ClaimEvidence`
- `AdVariant`
- `CreativeMessageBrief`
- `PlatformCopySet`
- `ComplianceRisk`
- `AdCopyQualityReport`
- `AdCopyCreationPackage`

Shared status, evidence, risk, cost, and handoff models should be reused if `packages/digital_marketing` is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_ad_copy_inputs` | normalized request | missing fields and blockers | None | Local only |
| `extract_claims_and_evidence` | offer/copy/evidence notes | claim inventory and missing evidence | None | Local only |
| `detect_forbidden_ad_actions` | request text | activation/spend/upload hard-fail flags | None | Local only |
| `detect_protected_targeting` | audience/copy text | protected attribute flags | None | Local only |
| `check_copy_constraints` | variants and supplied limits | length/format warnings | None | Local only |
| `score_ad_copy_package` | variants, evidence, risks | quality report | None | Local only |

No ad platform, audience platform, analytics, CRM, MAP, CMS, policy API, or live web tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No long-term creative memory in v1.
- Past approved ads may be supplied directly by the user as context.
- Optional package persistence must go through `ObjectStorage`.

## 11. Validation Strategy

- Require campaign goal, audience, offer, and at least one platform or format.
- Require claim evidence for strong claims; otherwise flag unsupported claims.
- Hard-flag protected targeting, deceptive urgency, policy bypass, launch/upload/spend requests, and regulated claims without evidence.
- Verify that each pass-case output has multiple variants and human review notes.
- Validate platform constraints only when constraints are supplied; do not invent current platform limits.

## 12. Quality Scoring Strategy

Agent 16 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Audience and offer alignment | 15 |
| Message angle distinctness | 15 |
| Platform and format fit | 15 |
| Claim evidence and compliance safety | 20 |
| Copy clarity and CTA strength | 15 |
| A/B test usefulness | 10 |
| Risk handling and review readiness | 10 |

Pass if score >= 82 and no hard-fail risk.

## 13. Evaluation Strategy

Eval datasets should cover strong evidence, missing evidence, search ads, paid social ads, regulated claims, deceptive urgency, protected targeting, launch/upload requests, and prompt injection in examples.

CI gates:

- schema_valid = 100%
- unsupported_claim_detection = 100% on hard-fail cases
- no_activation_behavior = 100%
- protected_targeting_safety = 100%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 14. Error Handling Strategy

- Missing required context returns `needs_human`.
- Hard-fail policy or activation requests block `pass`.
- Cost stop returns `stopped_cost_ceiling` with any safe claim/evidence findings.
- Provider failure returns `error` with redacted category and preserved cost usage.
- Invalid generated structure returns `needs_human` or `error` depending on whether safe partial output exists.

## 15. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, claim inventory, risk detection, generation, constraint checks, scoring, and finalization
- token/cost metrics by stage
- variant count, claim warning count, platform warning count, quality score, risk counts
- no raw customer records, PII, spend data, unreleased claims, or full pasted examples in logs

## 16. Prompt Strategy

- User-provided notes, reports, keyword tables, ad copy, page copy, campaign exports, metric summaries, and upstream handoffs are untrusted data.
- Untrusted text must be fenced and delimiter-escaped before it enters any model prompt.
- User-supplied data must never override system or developer instructions.
- The model must not invent metrics, search volume, CPC, rankings, claims, budget results, conversion lift, or live platform data.
- Recommendations must cite supplied evidence or be labeled as assumptions or heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

## 17. Cloud Agnostic Review

- Model calls only through `LLMProvider`.
- Optional persistence only through `ObjectStorage`.
- Secrets through `SecretStore`.
- Observability through `Telemetry`.
- No `google.cloud`, `vertexai`, `boto3`, `botocore`, Azure SDK, ad platform SDK, policy API SDK, direct model SDK, or `litellm` import inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents; Bedrock and Azure remain config/stub compatible.
- Shared `packages/digital_marketing` logic must receive its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render copy variants by channel, highlight unsupported claims, show evidence mapping, compare message angles, and let users pass approved variants as structured context to Agent 18, Agent 19, and Agent 21.

## 19. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine with an Agent 16 profile. The profile should define copy formats, claim-evidence requirements, forbidden activation actions, quality dimensions, platform-fit rules, and eval cases. Future versions may add deeper deterministic tools for platform-specific character rules or policy integrations only through separate provider-neutral designs.
