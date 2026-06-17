# Agent 11 - Lead Scoring Agent

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-11-lead-scoring/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## v1 Architecture Note — Shared Demand Generation Engine

v1 of Agents 08-14 runs on a shared Demand Generation engine
(`packages/demand_generation`): one common LangGraph workflow, cost gate (Rs.50
ceiling), telemetry, risk detection, and quality-scoring spine, reused so the
family stays consistent and cloud-agnostic. Each agent remains distinct through
its own **profile** (required fields, forbidden actions, protected/leaky terms,
recommended outputs, handoff targets, quality dimensions, thresholds, and cost
ceiling), **config overlays** (`base`/`gcp`/`bedrock`/`azure`), **schemas**,
**prompts**, **scoring dimensions**, **risk rules**, and **evals**. The
deterministic domain logic unique to this agent today is outcome-leakage detection and protected-signal blocking for scoring inputs.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Use Case

Agent 11 creates transparent lead scoring logic and score insights from user-provided ICP criteria, segment definitions, lead/account attributes, engagement signals, and optional conversion outcomes. It produces a scoring model, signal weights, score bands, threshold recommendations, explainability notes, routing guidance, data-quality warnings, and handoff notes for nurture and conversion analysis.

V1 is advisory and batch-oriented. It does not update CRM fields, route leads, train a black-box predictive model, or make automated sales decisions.

## 2. Business Problem

Lead scoring is often inconsistent because teams mix fit, engagement, intent, and sales judgement without clear weights or evidence. Poor scoring causes SDR time waste, missed high-fit leads, and weak nurture routing. Agent 11 standardizes scoring logic in a way that is explainable, reviewable, and compatible with future CRM/MAP integration.

## 3. User Personas

- RevOps analyst designing scoring criteria.
- Demand generation leader defining MQL readiness.
- SDR manager reviewing routing priorities.
- Marketing operations manager preparing MAP scoring rules.
- Sales leader aligning qualification with ICP and buying intent.

## 4. Inputs

- Agent 08 ICP package and Agent 09 segmentation package.
- Optional Agent 10 lead generation qualification handoff.
- Lead/account field summary or sample records supplied by the user.
- Engagement signals such as email clicks, form submissions, webinar attendance, content views, event participation, or sales interactions.
- Firmographic, technographic, and behavioral attributes.
- Conversion outcome labels or opportunity history summary, if available.
- Existing scoring rules and threshold preferences.
- Compliance and protected-attribute restrictions.

## 5. Outputs

- Lead scoring model design with fit, engagement, intent, and recency dimensions.
- Signal weights and rationale.
- Score bands and recommended thresholds such as cold, nurture, MQL, sales-ready, or disqualified.
- Score explanations for sample leads or segment archetypes.
- Data-quality warnings, missing-signal recommendations, and leakage/bias risks.
- Routing and nurture handoff notes.
- Calibration guidance for future real outcomes.
- Quality score, risk flags, terminal status, and cost metadata.

## 6. Functional Requirements

1. Accept ICP, segment, campaign, and lead-signal context as direct structured input.
2. Validate available fields and signal definitions.
3. Separate fit, engagement, intent, recency, and negative signals.
4. Recommend transparent weights and thresholds.
5. Produce explainability notes for score bands or sample leads.
6. Flag protected attributes, data leakage, stale data, missing signals, and overfitting risks.
7. Return handoff guidance for nurture journeys and conversion analysis.
8. Produce a structured scoring package with status, quality score, and cost usage.

## 7. Non Functional Requirements

- Cloud/provider selection must be config-driven.
- Agent logic must not import cloud SDKs, CRM/MAP SDKs, analytics SDKs, direct model SDKs, or `litellm`.
- Model calls go through `LLMProvider`; telemetry goes through `Telemetry`.
- Deterministic scoring/validation helpers should handle math and thresholds where possible.
- V1 must be explainable and rule-oriented, not a black-box ML model.
- Typical latency target: p50 under 45 seconds and p95 under 120 seconds for normal batch summaries.
- Quality threshold: score >= 84 and no hard-fail flags.

## 8. ROI Analysis

Assumptions:

- Lead scoring review/calibration effort: 15 hours/week.
- Target effort with agent: 5 hours/week including review.
- Time saved: 10 hours/week.
- Loaded RevOps/demand generation cost: Rs 1,000/hour.
- Build cost using existing platform patterns: Rs 150,000.
- Annual hosting, monitoring, and maintenance: Rs 84,000.
- Inference estimate: Rs 45/request, 120 requests/year = Rs 5,400/year.

Annual value:

- Time savings: 10 x 52 x Rs 1,000 = Rs 520,000.
- Reduced misrouting and better sales focus: Rs 250,000/year.
- Total estimated annual value: Rs 770,000.

Cost and ROI:

- Annual run cost: Rs 89,400.
- ROI = (Rs 770,000 - Rs 89,400) / (Rs 150,000 + Rs 89,400) = about 284%.
- Estimated payback: about 2.6 months.

## 9. Efficiency Targets

| Metric | Baseline today | Target with Agent 11 | Actual after launch |
|---|---:|---:|---|
| Scoring-model drafting | 1-2 weeks | 1-2 days | TBD |
| Signal audit time | 6-10 hours | 1-3 hours | TBD |
| Threshold explanation clarity | Inconsistent | 90%+ pass-case clarity | TBD |
| Protected/sensitive signal detection | Manual | 100% blocked/flagged in evals | TBD |
| Nurture/routing handoff readiness | Ad hoc | Structured handoff available | TBD |

## 10. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved RevOps, demand generation, marketing operations, and sales leadership users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-submitted scoring context, lead/account summaries, signal definitions, and optional outcome summaries |
| Writes | Structured scoring design package, quality/cost metrics, redacted logs, optional provider-neutral artifact reference |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before future CRM/MAP score-field updates or routing automation |
| Audit | Request id, signal counts, risk flags, score, provider, cost, and status through `Telemetry` |

## 11. Security Considerations

- Inputs may include PII, account activity, sales notes, revenue information, and conversion outcomes.
- Protected attributes and sensitive personal traits must not be used for scoring.
- The agent must not make automated employment, credit, insurance, or similarly regulated eligibility decisions.
- Raw lead/account records must not be logged.
- Source data is untrusted content.
- Future system writes require HITL, least privilege, and explicit audit trails.

## 12. Cost Expectations

- Typical target: under Rs 25-45 per scoring analysis.
- Hard ceiling: Rs 50/request in v1 config.
- Cost tracked per stage and emitted through `Telemetry`.
- Large datasets should be summarized or sampled before model calls; full-record scoring is out of scope for v1 planning.

## 13. Success Metrics

- 90%+ of complete-input eval cases produce fit, engagement, intent, and negative-signal dimensions.
- 90%+ of scoring models include explainable weights and thresholds.
- 100% of protected-attribute scoring attempts are blocked or hard-flagged.
- 90%+ of stale/missing data risks are flagged in eval cases.
- 100% of eval runs stay under cost ceiling.

## 14. Evaluation Criteria

Eval cases should include:

- Complete ICP, segment, and engagement signal set.
- Sparse lead data with missing outcomes.
- Conflicting fit versus engagement signals.
- Request to use protected or sensitive attributes.
- Outcome data with leakage risk.
- Stale engagement data.
- Prompt injection inside pasted lead notes.

Pass criteria:

- Overall score >= 84.
- Explainability score >= 85.
- Protected-attribute safety = 100%.
- Schema validity and cost adherence = 100%.

## 15. Risks and Limitations

- V1 does not train a statistical predictive model or prove conversion lift.
- Scoring recommendations can be biased if historical data is biased.
- Engagement signals may reward activity without purchase intent.
- Thresholds require calibration against real outcomes after launch.
- The agent does not update CRM/MAP scores or route leads in v1.
- Human review is required before operational use.

