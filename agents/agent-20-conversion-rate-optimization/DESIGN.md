# Agent 20 - Conversion Rate Optimization Agent Design

## 1. Metadata

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-20-conversion-rate-optimization/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 20 creates a disciplined CRO diagnosis and experiment backlog from supplied context. It must separate hypotheses from proof, prioritize experiments transparently, and keep live experiment launch or website changes outside v1.

## 3. Agent Boundaries

In scope:

- Analyze supplied page/form/funnel context and qualitative notes.
- Create CRO hypotheses, recommendations, and experiment plans.
- Prioritize using ICE/PIE-style or similar transparent scoring.
- Flag data, sample-size, consent, privacy, and manipulation risks.

Out of scope:

- Live analytics reads, A/B platform writes, website changes, experiment launch, automatic personalization, CMS writes, or causal proof claims without supplied evidence.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_cro_context
3. validate_goal_data_and_denominators
4. diagnose_conversion_friction
5. generate_hypothesis_backlog
6. prioritize_experiments
7. create_measurement_plan
8. detect_launch_privacy_and_manipulation_risks
9. score_cro_package
10. assemble_conversion_rate_optimization_package
11. finalize_response
```

Deterministic stages include denominator checks, sample-size caveats, forbidden-action detection, transparent priority score arithmetic, and status mapping. LLM-assisted stages synthesize diagnosis, hypotheses, and experiment narratives from supplied context.

## 5. State Model

Request-scoped state should contain:

- normalized CRO context
- supplied metrics and caveats
- friction diagnosis
- hypothesis backlog
- prioritization scores
- experiment plan
- measurement plan
- privacy/consent/manipulation risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain analytics clients, A/B testing clients, CMS clients, browser handles, or provider SDK objects.

## 6. Inputs

Primary input concepts:

- conversion goal, audience/segment, page/form/funnel context
- supplied baseline and denominator data
- Agent 14, 17, and 18 handoffs
- qualitative notes, objections, user feedback summaries
- constraints, privacy/consent notes, traffic/source/device context

## 7. Outputs

Primary output concepts:

- `ConversionRateOptimizationPackage`
- `CRODiagnosis`
- `CROHypothesis`
- `ExperimentPlan`
- `PrioritizationScore`
- `MeasurementPlan`
- `SampleSizeCaveat`
- `FrictionRecommendation`
- `PrivacyRisk`
- `DigitalMarketingHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `ConversionRateOptimizationRequest`
- `ConversionGoal`
- `FrictionFinding`
- `CROHypothesis`
- `PrioritizationRubric`
- `ExperimentBacklogItem`
- `MeasurementPlan`
- `CROQualityReport`
- `ConversionRateOptimizationPackage`

Shared status, cost, evidence, risk, and handoff contracts should be reused.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_cro_inputs` | request | missing context and blockers | None | Local only |
| `check_denominators_and_samples` | supplied metrics | caveats and undefined-rate warnings | None | Local only |
| `score_experiment_priority` | impact/confidence/effort inputs | transparent priority scores | None | Local only |
| `detect_forbidden_cro_actions` | request text | launch/change/personalize hard-fail flags | None | Local only |
| `detect_deceptive_or_privacy_risks` | recommendations/request | risk flags | None | Local only |
| `score_cro_package` | hypotheses and risks | quality report | None | Local only |

No analytics, A/B testing, CMS, personalization, browser, CRM, MAP, ad platform, or warehouse tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No persistent CRO memory in v1.
- Historical experiments can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require conversion goal, page/form/funnel context, audience, and either data or qualitative evidence.
- Flag missing denominators, small sample sizes, and unsupported lift claims.
- Hard-flag requests to launch experiments, change sites, ignore consent/privacy, or manipulate users deceptively.
- Ensure every hypothesis has rationale, evidence/source note, expected metric, owner/action guidance, and priority score.
- Mark causal claims as hypotheses unless supplied experiment data supports them.

## 12. Quality Scoring Strategy

Agent 20 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Diagnosis specificity and evidence use | 20 |
| Hypothesis quality | 20 |
| Prioritization transparency | 15 |
| Measurement plan quality | 15 |
| Data/sample caveat handling | 10 |
| Form/CTA/content/friction actionability | 10 |
| Privacy, consent, and manipulation safety | 10 |

Pass if score >= 84 and no hard-fail risk.

## 13. Evaluation Strategy

Eval datasets should cover complete CRO plan, missing denominator, small sample, unsupported lift claim, launch request, website-change request, consent bypass, deceptive manipulation, and prompt injection.

CI gates:

- schema_valid = 100%
- no_launch_or_site_change_behavior = 100%
- data_caveat_detection >= 90%
- hypothesis_quality >= 85 on complete cases
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 14. Error Handling Strategy

- Missing minimum CRO context returns `needs_human`.
- Missing denominator or sample limits return caveats and may return `needs_human`.
- Forbidden launch/change/privacy-bypass requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with safe partial diagnosis.
- Provider failure returns `error` with redacted category and preserved cost.

## 15. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for validation, diagnosis, hypothesis generation, prioritization, measurement plan, scoring, finalization
- token/cost by stage
- hypothesis count, high-priority count, caveat count, quality score, risk counts
- no raw lead records, user feedback snippets, revenue data, PII, or page copy in logs

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
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No cloud SDKs, analytics SDKs, A/B testing SDKs, CMS SDKs, personalization SDKs, browser/crawler SDKs, CRM/MAP SDKs, direct model SDKs, or `litellm` inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents; Bedrock and Azure remain config/stub compatible.
- Shared `packages/digital_marketing` logic must get its own no-cloud-SDK test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render CRO hypotheses as a backlog with priority scores, caveats, status, risk flags, and measurement plans. Studio should support human editing and later handoff to implementation tools only after a separate integration design.

## 19. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine with an Agent 20 profile. The profile should define hypothesis output sections, priority score rules, data caveats, launch/change hard-fails, quality dimensions, and eval cases. Future versions may add deeper local statistical calculators, but live analytics/testing writes remain out of v1.
