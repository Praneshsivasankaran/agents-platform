# Digital Marketing Batch Plan - Agents 15-21

**Status:** Phase 1/2 approved baseline; Phase 3 coding in progress
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Category:** Digital Marketing
**Scope:** Phase 1 and Phase 2 baseline for Agents 15-21; Phase 3 implements the approved shared Digital Marketing engine pattern.

---

## 1. Batch Goal

Prepare the Digital Marketing agent batch without starting implementation. This batch defines seven advisory agents that turn supplied marketing context, campaign plans, keyword lists, ad copy, landing page notes, paid performance summaries, conversion observations, and stakeholder reporting needs into structured review packages.

The Phase 1/2 deliverables were `AGENT_SPEC.md`, `DESIGN.md`, and this batch plan. Phase 3 may add Python files, tests, config overlays, Dockerfiles, CI changes, and a shared `packages/digital_marketing` package. No standalone UI apps are part of this batch; future rendering belongs in MarketingIQ Studio.

## 2. Why Digital Marketing Follows Demand Generation

Demand Generation Agents 08-14 established the upstream GTM planning layer: ICPs, audience segments, lead generation blueprints, scoring rules, campaign recommendations, nurture journeys, and conversion analysis. Digital Marketing should sit after that layer and convert selected strategies into practical digital execution plans and optimization packages.

This batch should reuse Demand Generation outputs as direct structured context where useful, but no Digital Marketing agent should directly import another agent. Handoffs remain structured data passed by users, orchestrators, or future MarketingIQ Studio workflows.

## 3. Agents Included

| Agent | Name | Path | Primary job |
|---|---|---|---|
| Agent 15 | Keyword Research Agent | `agents/agent-15-keyword-research` | Build keyword strategy from supplied context and data |
| Agent 16 | Ad Copy Creation Agent | `agents/agent-16-ad-copy-creation` | Draft safe ad variants and message briefs |
| Agent 17 | Landing Page Optimization Agent | `agents/agent-17-landing-page-optimization` | Improve supplied landing page strategy and copy |
| Agent 18 | Paid Campaign Optimization Agent | `agents/agent-18-paid-campaign-optimization` | Recommend paid campaign optimizations from supplied metrics |
| Agent 19 | Multi-Channel Campaign Planning Agent | `agents/agent-19-multi-channel-campaign-planning` | Convert chosen campaign direction into channel execution plans |
| Agent 20 | Conversion Rate Optimization Agent | `agents/agent-20-conversion-rate-optimization` | Produce CRO recommendations and experiment plans |
| Agent 21 | Performance Reporting Agent | `agents/agent-21-performance-reporting` | Create stakeholder-ready reports from supplied metrics |

## 4. Common Reusable Components

All seven agents should preserve the platform foundation:

- LangGraph orchestration with explicit terminal status handling.
- `LLMProvider` for all model calls through LiteLLM-backed provider selection.
- `ObjectStorage` for optional artifact persistence only.
- `SecretStore` for provider credentials.
- `Telemetry` for spans, logs, token/cost metrics, risk metrics, quality scores, and status.
- Pydantic contracts for request, output package, quality report, risk flags, cost usage, and downstream handoff objects.
- Shared cost ledger and `stopped_cost_ceiling` behavior.
- No-cloud-SDK import guard over `agents/*/agent/`.
- If a shared package is created in Phase 3, a separate banned-import test must scan `packages/digital_marketing`.
- Request-scoped state only.
- Draft/advisory output with human approval before external activation.

## 5. Possible Shared Digital Marketing Engine Design

V1 may use a shared Digital Marketing engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

A realistic common workflow is:

```text
intake_request
normalize_context
validate_minimum_inputs
detect_forbidden_actions_and_policy_risks
run_deterministic_domain_checks
generate_or_refine_recommendations
score_quality
assemble_package
finalize_response
```

This mirrors the accepted Demand Generation pattern without promising seven deeply bespoke engines before the implementation phase proves that complexity is warranted.

## 6. What Should Be Shared

Recommended shared concepts:

- `DigitalMarketingRequestMetadata`: tenant-safe request id, requested depth, max cost override, source labels.
- `DigitalMarketingContext`: business goal, product, offer, audience, region, funnel stage, campaign objective.
- `ChannelContext`: channel, platform constraints, placement, targeting restrictions, metric labels.
- `EvidenceItem`: supplied source label, supported claim, confidence, sensitivity.
- `RiskFlag`: category, severity, message, evidence needed, human-review requirement.
- `QualityReport`: overall score, dimension scores, approval reason, revision notes, hard-fail flags.
- `CostUsage`: per-stage costs, token counts, provider tier, total INR, ceiling INR.
- `DigitalMarketingHandoff`: target agent, structured fields, assumptions, blockers.
- `PolicyConstraint`: platform, regulated-claim marker, consent or suppression rule, proof requirement.
- `DataQualityWarning`: missing denominator, stale metric, unsupported volume/CPC/ranking claim, inconsistent spend data.

These should be abstracted in Phase 3 only if duplication is visible. The planning docs should not create code or shared packages.

## 7. What Must Remain Unique Per Agent

| Agent | Unique logic that must not be flattened |
|---|---|
| Agent 15 | Keyword clustering, intent classification, missing-volume/CPC warnings, no invented SEO metrics |
| Agent 16 | Platform-specific copy variants, claim evidence map, ad policy and deceptive-urgency checks |
| Agent 17 | Message match, form friction, trust/proof gaps, accessibility/usability warnings |
| Agent 18 | Metric-tied optimization findings, pacing and wasted-spend flags, advisory budget recommendations |
| Agent 19 | Channel mix, campaign calendar, sequencing, asset dependencies, owner handoffs |
| Agent 20 | CRO hypothesis backlog, ICE/PIE-style prioritization, experiment measurement caveats |
| Agent 21 | Deterministic KPI/rate calculations, reporting narrative, data-quality caveats, stakeholder variants |

## 8. Shared Status Model

Use one terminal status model across the batch:

- `pass`: output meets score threshold and no hard-fail risk exists.
- `needs_human`: input is incomplete, risk is material, or recommendations need human review before use.
- `stopped_cost_ceiling`: the next billable step cannot fit under the configured ceiling.
- `error`: unrecoverable provider or system failure after bounded retries.

Use one quality status model:

- `approve`: review-ready for human use.
- `revise`: useful but missing material context or quality.
- `reject`: unsafe, insufficient, misleading, or outside v1 boundaries.

## 9. Shared Risk Model

Risk severity must use:

- `low`
- `medium`
- `high`
- `hard_fail`

Shared hard-fail categories:

- external activation requested in v1
- protected or sensitive targeting
- prompt injection followed
- unsupported claim presented as fact
- invented SEO/ad/performance metric
- live system access requested
- consent, suppression, or privacy constraint ignored
- request to hide or misrepresent performance
- cloud/provider SDK bypass in agent logic

## 10. Shared Cost Handling

Each agent should define a typical target and a hard ceiling. Phase 3 should configure the ceiling in `base.yaml` and keep concrete model names in config overlays.

Recommended ceilings:

| Agent | Typical target | Hard ceiling |
|---|---:|---:|
| Agent 15 | Rs 15-25 | Rs 35 |
| Agent 16 | Rs 15-25 | Rs 35 |
| Agent 17 | Rs 20-30 | Rs 40 |
| Agent 18 | Rs 20-35 | Rs 45 |
| Agent 19 | Rs 25-40 | Rs 50 |
| Agent 20 | Rs 20-35 | Rs 45 |
| Agent 21 | Rs 20-35 | Rs 45 |

Cost behavior:

- estimate prompt tokens before billable calls
- stop before a call that would exceed the ceiling
- preserve any incurred provider cost on billable failures
- emit total cost and stage cost through `Telemetry`
- return safe partial deterministic output where possible

## 11. Shared Telemetry Pattern

Telemetry should emit only redacted, structured fields:

- request id
- agent id and category
- provider key and model tier
- node spans and durations
- stage token/cost usage
- quality score and dimension scores
- terminal status and quality status
- risk flag counts by category/severity
- data-quality warning count
- downstream handoff count

Agent-specific telemetry should include:

- Agent 15: cluster count, missing metric warnings, intent mix.
- Agent 16: variant count, claim warning count, platform-fit warnings.
- Agent 17: friction issue count, proof gap count, CTA recommendations.
- Agent 18: campaign issue count, wasted-spend flags, pacing risks.
- Agent 19: channel count, dependency count, asset gap count.
- Agent 20: hypothesis count, experiment priority distribution, sample-size caveats.
- Agent 21: KPI count, deterministic calculation count, data-quality caveats.

No raw keyword lists with sensitive strategy, pasted landing page copy, ad spend tables, revenue data, lead records, emails, phone numbers, or account records should be logged.

## 12. Shared Eval Strategy

Every agent should include eval cases for:

- complete happy path
- sparse/incomplete input
- conflicting constraints
- prompt injection inside pasted context
- protected/sensitive targeting or policy violation
- forbidden external activation request
- cost ceiling behavior
- schema validity

Shared CI-style thresholds:

- schema validity = 100%
- no forbidden activation behavior = 100%
- prompt-injection resistance = 100%
- protected/sensitive targeting safety = 100% where relevant
- cost ceiling adherence = 100%
- pass rate on complete-input cases >= 80%
- agent-specific quality threshold met on pass cases

Agent-specific assertions must be present. Examples: Agent 15 must not invent search volume or CPC; Agent 21 must calculate simple rates and deltas only from supplied denominators.

## 13. Agent-By-Agent Implementation Complexity

| Agent | Complexity | Rationale |
|---|---|---|
| Agent 15 | Medium | Structured clustering and no-metric-fabrication checks matter |
| Agent 16 | Medium | Multiple copy formats plus claim/policy safety |
| Agent 17 | Medium | Page strategy review with friction and proof-gap scoring |
| Agent 18 | Medium-High | Metric-tied paid recommendations and advisory budget constraints |
| Agent 19 | Medium-High | Many handoffs, channels, owners, calendar and asset dependencies |
| Agent 20 | High | Experiment prioritization, measurement caveats, sample-size discipline |
| Agent 21 | High | Deterministic reporting math plus causal/misrepresentation guardrails |

## 14. Recommended Implementation Order

1. Agent 15 - Keyword Research Agent
2. Agent 16 - Ad Copy Creation Agent
3. Agent 17 - Landing Page Optimization Agent
4. Agent 18 - Paid Campaign Optimization Agent
5. Agent 19 - Multi-Channel Campaign Planning Agent
6. Agent 20 - Conversion Rate Optimization Agent
7. Agent 21 - Performance Reporting Agent

Reasoning:

- Agent 15 provides keyword and intent context for ad copy, landing pages, paid search, and planning.
- Agent 16 turns audience, offer, and keyword context into message variants.
- Agent 17 converts copy and keyword themes into page recommendations.
- Agent 18 uses keyword, copy, page, and performance summaries for paid optimization.
- Agent 19 coordinates the prior outputs into execution planning.
- Agent 20 uses page and paid/conversion context for CRO experiment design.
- Agent 21 closes the loop by reporting supplied metrics and carrying lessons forward.

## 15. Relationship To Agents 08-14

Expected handoffs:

- Agent 15 can consume Agents 08, 09, and 12 outputs.
- Agent 16 can consume Agents 09, 10, 12, and 15 outputs.
- Agent 17 can consume Agents 10, 12, 15, and 16 outputs.
- Agent 18 can consume Agents 12, 15, 16, 17, and supplied paid performance data.
- Agent 19 can consume Agents 08, 09, 10, 12, 15, 16, 17, and 18 outputs.
- Agent 20 can consume Agents 14, 17, 18, and supplied page/form/funnel context.
- Agent 21 can consume Agents 12, 14, 18, 20, and supplied campaign metrics.

Avoid overlap:

- Agent 12 recommends and ranks campaign plays; Agent 19 turns a chosen direction into a coordinated execution plan.
- Agent 14 analyzes conversion/funnel data; Agent 20 designs CRO experiments and optimization actions.
- Agent 10 creates a lead-generation blueprint; Agent 17 evaluates message match, page clarity, and conversion friction.
- Agent 18 recommends paid optimization actions; Agent 21 creates stakeholder-ready performance reporting.

## 16. Relationship To Future MarketingIQ Studio

Do not design standalone UI apps in this phase. Each Digital Marketing agent should return structured outputs that can later render inside MarketingIQ Studio under the Digital Marketing tab.

Future Studio should be able to show:

- quality score and quality status
- terminal status
- risk flags by severity
- missing evidence/data warnings
- structured recommendations
- downstream handoffs
- cost metadata
- human review notes

## 17. Coding-Phase Recommendations

Phase 3 should:

- start by confirming whether to create `packages/digital_marketing`
- use profile-driven differentiation if a shared engine is chosen
- add banned-import tests for any shared digital marketing package
- mirror base/gcp/bedrock/azure config overlays from Agents 08-14
- add GCP provider construction tests and optional live GCP smoke tests gated by env vars
- keep Bedrock/Azure stub compatibility
- use deterministic local checks for math, policy, data quality, forbidden actions, and scoring support
- keep live SEO tools, ad platforms, analytics, Search Console, CMS, CRM, MAP, and A/B testing systems out of v1

## 18. Risks To Watch

- Doc-code divergence if docs promise bespoke deterministic workflows but Phase 3 uses a shared engine.
- Metric fabrication, especially search volume, CPC, keyword difficulty, ranking, spend, ROAS, and conversion lift.
- Protected-attribute targeting hidden inside audience or ad-copy requests.
- Prompt injection inside pasted keyword lists, reports, landing page copy, campaign data, and analytics notes.
- Raw PII, spend, revenue, or account data leaking into logs.
- Scope creep into activation: launching ads, changing budgets, publishing pages, sending reports, uploading audiences, or running experiments.

## 19. Explicit Warning Against Doc-Code Divergence

The docs must stay implementation-aligned. If Phase 3 uses a shared engine, the implementation must not be reviewed against a fantasy design that promised seven bespoke deep workflows. The correct v1 bar is a cloud-neutral shared platform spine with agent-specific profiles, schemas, prompts, risk rules, scoring dimensions, deterministic helpers, and evals.

If a later agent genuinely needs deeper deterministic workflow nodes, add them deliberately and document the reason.

## 20. Recommendation On `packages/digital_marketing`

Yes: Phase 3 should strongly consider a shared `packages/digital_marketing` package, modeled after `packages/demand_generation`, if the first two agents show common mechanics.

Recommended shared package scope:

- shared request/package concepts
- status, quality, cost, evidence, risk, and handoff schemas
- common prompt fencing and escaping helpers
- forbidden-action and protected-targeting detection
- data-quality and metric-fabrication checks
- shared scoring helpers
- shared LangGraph workflow spine
- profile registry for Agents 15-21
- no-cloud-SDK test over the shared package

Keep these unique per agent: required inputs, output package shape, quality rubric, hard-fail rules, deterministic domain checks, eval cases, and handoff targets.
