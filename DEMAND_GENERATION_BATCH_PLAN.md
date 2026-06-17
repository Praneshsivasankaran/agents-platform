# Demand Generation Batch Plan - Agents 08-14

**Status:** Draft for architecture review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Category:** Demand Generation
**Scope:** Phase 1 and Phase 2 planning only for Agents 08-14

---

## 1. Common Reusable Components Across All 7 Agents

All Demand Generation agents should reuse the existing platform foundation:

- LangGraph orchestration with explicit node flow and terminal status funnel.
- `LLMProvider` for all model calls through LiteLLM-backed provider selection.
- `ObjectStorage` for optional artifact persistence.
- `SecretStore` for provider credentials.
- `Telemetry` for spans, logs, token/cost metrics, quality metrics, and status.
- Shared cost ledger, cost guard, and `stopped_cost_ceiling` behavior.
- Shared no-cloud-SDK import guard for `agents/*/agent/`.
- Shared eval harness in `packages/evals`.
- Request-scoped state only unless a future design explicitly justifies memory.
- Draft/planning-only outputs with human approval before external activation.

The image-provided Demand Generation lane also includes account-based marketing support, landing page recommendations, campaign optimization, and lead scoring insights. In this batch those capabilities are intentionally distributed across the seven requested agents instead of adding new agents:

- Account-based marketing support: Agents 08, 09, 10, and 11.
- Landing page recommendations: Agent 10.
- Campaign optimization: Agents 12 and 14.
- Lead scoring insights: Agent 11.

## 2. Shared Schemas That Could Be Abstracted

Recommended shared Demand Generation schema concepts:

- `DemandGenRequestMetadata`: tenant/user-safe ids, requested output depth, cost override, source labels.
- `BusinessContext`: product/service, market, region, pricing/packaging, sales motion.
- `CampaignContext`: objective, funnel stage, offer, timeline, budget, region, channel constraints.
- `ICPProfile`: fit criteria, disqualifiers, buying committee, confidence, evidence refs.
- `AudienceSegment`: inclusion rules, exclusion rules, segment rationale, message guidance.
- `LeadSignal`: signal name, category, source, freshness, reliability, allowed/forbidden flag.
- `ScoreBand`: label, threshold, rationale, recommended action.
- `ChannelPlan`: channel, objective, budget guidance, KPI, dependencies.
- `JourneyTouchpoint`: stage, channel, timing, content, CTA, owner, exit condition.
- `FunnelMetric`: stage, count, rate, denominator, period, segment.
- `EvidenceItem`: source label, claim supported, confidence, sensitivity.
- `RiskFlag`: category, severity, message, evidence needed, human-review requirement.
- `QualityReport`: overall score, dimension scores, pass/fail, hard-fail flags, revision notes.
- `CostUsage`: stage costs, token usage, provider, total INR, ceiling INR.
- `DemandGenHandoff`: intended downstream agent, structured fields, assumptions, blockers.

These should be abstracted only when implementation begins and duplication becomes visible. Planning docs should not create shared code.

## 3. Shared Workflow Patterns

Common graph pattern:

```text
intake_request
normalize_context
validate_minimum_inputs
extract_or_classify_domain_signals
generate_candidate_outputs
deterministically_validate_candidates
score_quality
assemble_package
finalize_response
```

Common terminal statuses:

- `pass`: output meets score threshold and has no hard-fail flags.
- `needs_human`: input is incomplete, risk is material, or recommendations need review before use.
- `stopped_cost_ceiling`: next billable step cannot fit under the configured ceiling.
- `error`: unrecoverable provider or system failure after bounded retries.

Common hard-fail categories:

- external activation requested in v1
- protected-attribute targeting or scoring
- prompt injection followed
- unsupported claims presented as fact
- consent/suppression constraint ignored
- cloud/provider SDK imported or bypassed in agent logic

## 4. Shared Evaluation Patterns

Every agent should include eval cases for:

- complete happy path
- sparse/incomplete input
- conflicting constraints
- prompt injection inside pasted notes
- protected-attribute or sensitive targeting/scoring attempt
- request for forbidden external activation
- cost ceiling behavior
- schema validity

Shared CI-style thresholds:

- schema validity = 100%
- no forbidden activation behavior = 100%
- protected-attribute safety = 100% where relevant
- cost ceiling adherence = 100%
- pass rate on complete-input cases >= 80%
- agent-specific quality score threshold met on pass cases

Each agent still needs its own domain checks. For example, Agent 14 needs metric math correctness, while Agent 08 needs evidence traceability.

## 5. Shared Telemetry Patterns

All telemetry should flow through `Telemetry` and avoid raw sensitive payloads.

Common telemetry:

- run/request id
- agent id and category
- provider key and model tier
- node span names and durations
- stage token/cost usage
- quality score and dimension scores
- risk flag counts by coarse category
- terminal status
- cost ceiling and total cost

Agent-specific telemetry:

- Agent 08: ICP count, evidence sufficiency, assumption count.
- Agent 09: segment count, overlap warnings, suppression count.
- Agent 10: selected campaign motion, capture-path completeness.
- Agent 11: signal counts by category, forbidden-signal count.
- Agent 12: campaign option count, selected play, dependency count.
- Agent 13: journey branch count, touchpoint count, content gap count.
- Agent 14: funnel stage count, bottleneck count, data-quality warning count.

## 6. Shared Provider Usage Patterns

- Use `LLMProvider` for all model calls.
- Resolve concrete models by config overlays, never inside agent logic.
- Use cheap/standard model tiers for normalization and classification where suitable.
- Use stronger model tiers for final recommendation, reasoning, or synthesis stages.
- Use deterministic local tools for validation, scoring support, metric math, overlap checks, weight normalization, and cost estimation.
- Do not use `TranscriptionProvider` in v1 for this batch because all requested Demand Generation agents are text/structured-input agents. If future voice/video input is added, ADR-0003 applies.
- No external provider is needed for CRM, MAP, analytics, enrichment, ad platforms, or web search in v1.

## 7. Shared Quality Scoring Concepts

All agents should use 100-point transparent rubrics with:

- a pass threshold between 82 and 84 depending on risk
- hard-fail flags that override numeric scores
- dimension-level scores
- human-readable approval/revision notes
- deterministic scoring helpers where possible

Shared dimensions across the batch:

- input sufficiency
- evidence traceability
- strategic fit
- operational feasibility
- compliance and consent handling
- downstream handoff readiness
- clarity for human review
- cost-conscious execution

Unique dimensions remain agent-specific. ICP evidence strength is not the same as funnel metric correctness; those should not be collapsed into one generic score.

## 8. What Should Remain Unique Per Agent

| Agent | Unique business logic |
|---|---|
| Agent 08 - ICP Identification | Evidence-backed ICP creation, fit/disqualifier logic, buying committee mapping |
| Agent 09 - Audience Segmentation | Segment axes, overlap detection, suppression and audience-rule clarity |
| Agent 10 - Lead Generation | Offer/capture-path planning, landing page/form brief, qualification handoff |
| Agent 11 - Lead Scoring | Signal taxonomy, weight normalization, thresholds, explainability, bias/leakage checks |
| Agent 12 - Campaign Recommendation | Ranked campaign play comparison, channel/budget rationale, dependency planning |
| Agent 13 - Lead Nurturing | Journey branching, cadence, touchpoints, trigger/exit/suppression logic |
| Agent 14 - Conversion Analysis | Deterministic funnel math, bottleneck detection, data-quality caveats, experiment backlog |

## 9. Estimated Implementation Complexity Per Agent

| Agent | Complexity | Rationale |
|---|---|---|
| Agent 08 - ICP Identification | Medium | Mostly structured reasoning and evidence mapping; foundational schemas matter |
| Agent 09 - Audience Segmentation | Medium | Needs overlap/thin-segment validation and compliance checks |
| Agent 10 - Lead Generation | Medium | Requires campaign blueprint specificity and strict no-activation boundaries |
| Agent 11 - Lead Scoring | High | Requires signal taxonomy, threshold logic, protected-signal checks, and explainability |
| Agent 12 - Campaign Recommendation | Medium | Needs option scoring and dependency planning; no live systems in v1 |
| Agent 13 - Lead Nurturing | Medium-High | Journey branching, cadence, content gaps, and consent/suppression logic |
| Agent 14 - Conversion Analysis | High | Deterministic metric math, denominator validation, data-quality checks, and diagnosis |

Complexity assumes the existing scaffold, provider factory, eval harness, and no-cloud-SDK guard are reused.

## 10. Recommended Implementation Order

Recommended order:

1. Agent 08 - ICP Identification
2. Agent 09 - Audience Segmentation
3. Agent 10 - Lead Generation
4. Agent 11 - Lead Scoring
5. Agent 12 - Campaign Recommendation
6. Agent 13 - Lead Nurturing
7. Agent 14 - Conversion Analysis

Reasoning:

- Agent 08 establishes ICP and fit/disqualifier primitives.
- Agent 09 turns ICP into operational audience segments.
- Agent 10 uses ICP/segments to design the first lead generation blueprint.
- Agent 11 can then score leads using the ICP/segment/campaign handoffs.
- Agent 12 can recommend broader campaign plays after the core demand objects exist.
- Agent 13 uses segments, score bands, and campaign context to design nurture.
- Agent 14 closes the loop by analyzing performance after campaign/nurture structures are defined.

Before implementation begins:

- Confirm whether to generate these agents from the existing `new-agent` CLI or manually create only after a fresh scaffold review.
- Decide whether shared Demand Generation contracts should live in `packages/core`, a future `packages/marketingiq`, or stay per-agent until duplication is proven.
- Confirm cost ceilings and quality thresholds with the architect.
- Confirm whether MarketingIQ Studio will require a common package envelope across all MarketingIQ agents.
- Keep v1 free of external writes, live CRM/MAP/ad/analytics connectors, scraping, and autonomous enrichment.

