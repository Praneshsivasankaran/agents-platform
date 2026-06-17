# Agent 17 - Landing Page Optimization Agent Design

## 1. Metadata

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-17-landing-page-optimization/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 17 produces a structured landing page optimization brief from supplied page and campaign context. It focuses on message match, conversion clarity, proof, friction, usability, and safe human handoff without crawling, publishing, or reading live systems.

## 3. Agent Boundaries

In scope:

- Analyze supplied page copy, outlines, wireframe notes, or screenshot notes.
- Recommend improvements to hero, CTA, form, proof, section hierarchy, and page-to-ad relevance.
- Identify accessibility/usability warnings from supplied information.
- Produce A/B test ideas and implementation brief.

Out of scope:

- Website crawling, CMS writes, publishing, heatmap/session replay reads, live analytics, visual screenshot analysis, automatic personalization, or experiment launch.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_page_campaign_context
3. validate_page_material_and_goal
4. compare_ad_keyword_offer_message_match
5. review_hero_cta_form_and_proof
6. identify_hierarchy_accessibility_and_usability_risks
7. generate_page_recommendations
8. create_ab_test_ideas
9. build_implementation_brief
10. score_landing_page_package
11. assemble_landing_page_optimization_package
12. finalize_response
```

Deterministic checks cover required input, forbidden live actions, form-field count/friction heuristics, unsupported-claim markers, PII/consent warnings, and output completeness. LLM-assisted stages handle page review synthesis, section rewrite suggestions, and test idea framing.

## 5. State Model

Request-scoped state should contain:

- normalized page and campaign context
- supplied page sections or notes
- message-match findings
- CTA and form friction analysis
- proof gaps and trust signals
- accessibility/usability warnings
- recommendations and A/B ideas
- implementation brief
- risk flags
- quality report, cost ledger, terminal status, and final package

No provider SDK objects, browser handles, CMS clients, analytics clients, or raw provider responses may live in state.

## 6. Inputs

Primary input concepts:

- campaign objective, audience, offer, CTA goal
- supplied page copy/outline/wireframe/screenshot notes
- Agent 15 keyword research
- Agent 16 ad copy themes
- Agent 10 or Agent 12 campaign context
- form fields, compliance/privacy constraints, proof assets, objections, brand voice

## 7. Outputs

Primary output concepts:

- `LandingPageOptimizationPackage`
- `MessageMatchFinding`
- `HeroRecommendation`
- `CTARecommendation`
- `FormFrictionFinding`
- `ProofGap`
- `HierarchyRecommendation`
- `AccessibilityUsabilityWarning`
- `ABTestIdea`
- `ImplementationBrief`
- `DigitalMarketingHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `LandingPageOptimizationRequest`
- `LandingPageSection`
- `CampaignMessageContext`
- `MessageMatchReview`
- `FrictionFinding`
- `ProofRequirement`
- `PageRecommendation`
- `LandingPageQualityReport`
- `LandingPageOptimizationPackage`

Shared risk, evidence, status, cost, and handoff models should be reused if a shared package is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_page_inputs` | request | missing fields and blockers | None | Local only |
| `detect_forbidden_page_actions` | request text | crawl/publish/CMS hard-fail flags | None | Local only |
| `compare_message_terms` | ad/keyword/page text | overlap and mismatch hints | None | Local only |
| `review_form_friction` | supplied form fields | friction and consent warnings | None | Local only |
| `detect_deceptive_patterns` | page/copy text | manipulation risk flags | None | Local only |
| `score_landing_page_package` | findings and risks | quality report | None | Local only |

No CMS, browser crawler, analytics, heatmap, replay, A/B testing, ad platform, CRM, or MAP tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No long-term page memory in v1.
- Prior page versions can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require page material, campaign objective, audience, and offer/conversion goal.
- Flag missing page copy or only-URL requests as `needs_human` because v1 does not crawl.
- Hard-flag publish/CMS/update/crawl/analytics/heatmap requests.
- Hard-flag deceptive manipulation and unsafe PII collection.
- Ensure pass outputs include message match, CTA, proof, form/friction, and implementation notes.
- Mark measured-performance claims as unsupported unless data is supplied.

## 12. Quality Scoring Strategy

Agent 17 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Message match and offer clarity | 20 |
| Hero and CTA actionability | 15 |
| Form friction and conversion path review | 15 |
| Trust proof and objection handling | 15 |
| Content hierarchy and usability | 10 |
| SEO/ad relevance notes | 10 |
| Test ideas and implementation brief | 10 |
| Risk and privacy handling | 5 |

Pass if score >= 82 and no hard-fail risk.

## 13. Evaluation Strategy

Eval datasets should cover complete page copy, only URL/no page text, weak message match, excessive form fields, unsupported claim insertion, deceptive pattern request, crawl/CMS request, and prompt injection inside page text.

CI gates:

- schema_valid = 100%
- no_crawl_or_cms_behavior = 100%
- deceptive_pattern_safety = 100%
- required_section_coverage >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 14. Error Handling Strategy

- URL-only input returns `needs_human` with request for pasted copy/notes.
- Publish/CMS/crawl requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with safe deterministic findings.
- Provider failure returns `error` with redacted category and preserved cost.
- Conflicting page/ad context returns `needs_human` or competing hypotheses.

## 15. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, status
- spans for validation, message-match review, friction review, generation, scoring, finalization
- token/cost by stage
- finding counts by section, proof gap count, CTA recommendation count, quality score, risk count
- no raw page copy, lead form values, customer proof, or PII in logs

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
- No cloud SDKs, CMS SDKs, browser/crawler SDKs, analytics SDKs, heatmap/session tools, A/B testing SDKs, direct model SDKs, or `litellm` inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents; Bedrock and Azure remain config/stub compatible.
- Shared `packages/digital_marketing` logic must get its own banned-import test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render page-section findings, message-match matrix, form friction issues, proof gaps, A/B ideas, and implementation brief objects. Approved outputs should pass to Agent 20 for CRO planning and Agent 21 for reporting context.

## 19. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine with an Agent 17 profile. The profile should define page review sections, hard-fail live actions, message-match scoring dimensions, form-friction validation, and eval cases. Future versions may add deeper deterministic tools for local page diffing or accessibility checks, but live crawling and CMS writes remain separate future integrations.
