# Agent 11 - Lead Scoring Agent Design

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-11-lead-scoring/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## v1 Architecture Note — Shared Demand Generation Engine

The detailed node / tool / contract design below is the target shape. v1
implements it on a shared Demand Generation engine (`packages/demand_generation`)
— a common LangGraph workflow (intake_request -> analyze_context -> generate ->
score_quality -> assemble_package), cost gate, telemetry, risk detection, and
quality scoring — parameterized per agent by a **profile** plus this agent's own
**config overlays**, **schemas**, **prompts**, **scoring dimensions**, **risk
rules**, and **evals**. The deterministic domain logic unique to this agent today
is outcome-leakage detection and protected-signal blocking for scoring inputs; remaining recommendation content is produced by the model under the
agent's prompt and validated deterministically.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Purpose

Agent 11 designs transparent lead scoring logic from supplied ICP, segment, campaign, lead/account, and engagement context. It must prioritize explainability, data quality, compliance, and downstream handoff over black-box prediction.

## 2. Agent Boundaries

In scope:

- Recommend scoring dimensions, weights, thresholds, and score bands.
- Explain score drivers and data-quality limitations.
- Produce routing and nurture handoff notes.

Out of scope:

- CRM/MAP writes, lead routing, or automated status changes.
- Training a production ML model.
- Scoring millions of raw records inside the agent.
- Use of protected classes or sensitive personal traits.
- Live analytics, CRM, warehouse, or enrichment reads.

## 3. Workflow Overview

```text
1. intake_request
2. normalize_scoring_context
3. validate_signal_inventory
4. classify_fit_engagement_intent_recency_signals
5. detect_protected_or_leaky_signals
6. propose_weighting_model
7. define_score_bands_and_thresholds
8. explain_sample_scores_or_archetypes
9. generate_routing_and_nurture_handoff
10. validate_model_balance_and_data_quality
11. score_scoring_package_quality
12. assemble_lead_scoring_package
13. finalize_response
```

This workflow is more analytical than Agent 10: deterministic validation and scoring-rule math should carry as much work as possible.

## 4. State Model

Request-scoped state should contain:

- normalized ICP/segment/campaign context
- lead/account field inventory
- signal inventory grouped by type
- protected/leaky/stale signal flags
- proposed scoring dimensions and weights
- score bands and threshold recommendations
- sample score explanations or archetype examples
- routing/nurture handoff
- quality report, cost ledger, terminal status, and final package

No state object may contain CRM clients, raw provider responses, or provider SDK handles.

## 5. Inputs

Primary input concepts:

- ICP profile and segment definitions
- lead/account fields and engagement signal summary
- optional sample lead records or archetypes
- optional historical conversion/outcome summary
- existing scoring rules
- routing goals and threshold preferences
- compliance and protected-attribute restrictions

## 6. Outputs

Primary output concepts:

- `LeadScoringPackage`
- scoring dimensions and signal taxonomy
- signal weights and rationale
- score bands and thresholds
- sample explanations or archetype scores
- data-quality and bias risk warnings
- routing and nurture handoff
- quality report, risk flags, cost summary, and status

## 7. Pydantic Contract Concepts

Future contracts should include:

- `LeadScoringRequest`
- `LeadSignal`
- `SignalInventory`
- `ScoringDimension`
- `SignalWeight`
- `ScoreBand`
- `ThresholdRecommendation`
- `SampleScoreExplanation`
- `DataQualityWarning`
- `BiasRiskFlag`
- `RoutingHandoff`
- `LeadScoringQualityReport`
- `LeadScoringPackage`

Shared `RiskFlag`, `EvidenceItem`, `CostUsage`, and terminal-status concepts should be reused.

## 8. Tool Requirements

Local deterministic tools:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_signal_inventory` | Fields and signals | Completeness report and blockers | None | Local only |
| `classify_signal_type` | Signal definitions | Fit/engagement/intent/recency/negative categories | None | Local only |
| `detect_forbidden_signals` | Signal inventory | Protected, sensitive, or leaky signal flags | None | Local only |
| `normalize_weights` | Proposed weights | Weight totals and balance report | None | Local only |
| `score_lead_scoring_package` | Model, thresholds, risks | Quality report | None | Local only |
| `estimate_cost_usage` | Provider usage metadata | Cost ledger | None | Local only |

No CRM/MAP/warehouse/analytics/enrichment tool is allowed in v1.

## 9. Memory Requirements

- Request-scoped state only.
- No persistent lead memory in v1.
- Historical outcomes can be supplied as direct context.
- Optional artifact persistence must use `ObjectStorage`.
- Future calibration memory requires separate design because it may contain sensitive performance history.

## 10. Validation Strategy

- Require at least one fit signal and one engagement/intent signal for a pass-quality model.
- Reject protected or sensitive attributes as scoring inputs.
- Flag leakage where a signal directly encodes the outcome being predicted.
- Flag stale, missing, sparse, or unreliable data.
- Ensure weights total correctly and thresholds are logically ordered.
- Verify explainability notes exist for score bands or sample leads.

## 11. Quality Scoring Strategy

Agent 11 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Signal relevance and ICP alignment | 20 |
| Explainability of weights and thresholds | 15 |
| Data quality and completeness handling | 15 |
| Fit/engagement/intent balance | 15 |
| Bias, protected-attribute, and leakage safety | 10 |
| Routing and nurture actionability | 10 |
| Calibration guidance | 10 |
| Operational clarity | 5 |

Pass if score >= 84 and no hard-fail flags.

## 12. Evaluation Strategy

Eval datasets should cover complete signal sets, sparse data, protected-attribute requests, data leakage, conflicting fit/engagement, stale signals, and prompt injection in pasted records.

CI gates:

- schema_valid = 100%
- protected_signal_safety = 100%
- leakage_detection = 100% on leakage cases
- explainability_score >= 85
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 13. Error Handling Strategy

- Missing minimum signal inventory returns `needs_human`.
- Protected or leaky required signals force hard-fail flags.
- Impossible thresholds return `needs_human` with correction guidance.
- Cost stop returns `stopped_cost_ceiling` while preserving safe partial findings.
- Provider failure returns `error` with redacted category and preserved cost usage.

## 14. Telemetry Requirements

Emit through `Telemetry` only:

- request id, provider, model tier, terminal status
- spans for signal validation, forbidden-signal detection, weighting, thresholding, scoring, and finalization
- token/cost by billable stage
- signal counts by coarse type, warning counts, quality score, and status
- no raw lead records, email addresses, names, or account-level sensitive data in logs

## 15. Cloud Agnostic Review

- Model calls only through `LLMProvider`.
- Optional persistence only through `ObjectStorage`.
- Secrets through `SecretStore`; observability through `Telemetry`.
- No cloud, CRM/MAP, analytics, warehouse, enrichment, direct model, or `litellm` SDK imports inside `agent/`.
- GCP/Bedrock/Azure selection must remain config-only.

## 16. Future Integration Considerations

- MarketingIQ Studio should render scoring models, thresholds, and signal explanations as editable planning objects.
- Future CRM/MAP scoring deployment requires HITL, write-scope design, audit logs, and rollback behavior.
- Future model calibration could use conversion history through a separate provider-neutral data-access design.
- Agent 13 should consume score bands for nurture branching.
- Agent 14 should compare conversion outcomes against the scoring model for calibration feedback.

