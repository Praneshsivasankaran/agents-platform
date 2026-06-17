# Agent 09 - Audience Segmentation Agent

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-09-audience-segmentation/`
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
deterministic domain logic unique to this agent today is audience-size guarding (size estimates require supplied counts) and segment/suppression rule clarity.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Use Case

Agent 09 converts an ICP, campaign goal, and user-provided audience/account context into clear audience segments for demand generation campaigns. It produces segment definitions, inclusion/exclusion rules, pain points, buying-stage assumptions, channel fit, messaging guidance, suppression rules, and handoff notes for lead generation, scoring, campaign recommendations, and nurture programs.

V1 is a planning and classification agent. It does not upload audiences, mutate CRM lists, enrich records, or activate campaigns.

## 2. Business Problem

Campaigns often underperform because audiences are either too broad, too fragmented, or segmented by whatever data happens to be available rather than by campaign intent and buyer behavior. Agent 09 standardizes segmentation logic so downstream campaign planning, lead scoring, and nurture journeys begin with explicit, reviewable audience assumptions.

## 3. User Personas

- Demand generation manager preparing a campaign.
- Marketing operations specialist defining audience rules.
- Product marketer translating persona strategy into segment criteria.
- RevOps analyst checking segment feasibility and data availability.
- SDR leader aligning outreach cohorts with sales priorities.

## 4. Inputs

- Agent 08 ICP package or manually supplied ICP summary.
- Campaign objective, offer, funnel stage, and target geography.
- Audience/account list summary or user-provided fields.
- Available segmentation attributes such as industry, company size, role, lifecycle stage, engagement, product interest, and account tier.
- Exclusion/suppression criteria.
- Compliance, consent, and regional restrictions.
- Past campaign performance summaries supplied as direct context.

## 5. Outputs

- Prioritized audience segments with clear inclusion and exclusion rules.
- Segment rationale and estimated readiness/confidence.
- Segment pain points, motivations, objections, and message angles.
- Recommended channels, content types, and offer fit per segment.
- Suppression rules and compliance warnings.
- Data gaps and field requirements for marketing operations.
- Handoff notes for Agents 10, 11, 12, and 13.
- Quality score, risk flags, terminal status, and cost metadata.

## 6. Functional Requirements

1. Accept ICP packages and campaign context as direct structured input.
2. Normalize available audience fields and campaign objective.
3. Identify viable segmentation axes.
4. Generate mutually understandable audience segments.
5. Detect overlap, over-segmentation, thin segments, and conflicting rules.
6. Recommend message angles and channel fit per segment.
7. Produce suppression and compliance guidance.
8. Return a structured segmentation package with status and quality score.

## 7. Non Functional Requirements

- Cloud/provider selection is config-driven.
- Agent logic must remain cloud-neutral and must not import cloud, CRM, MAP, enrichment, ad-platform, or direct model SDKs.
- Model calls go through `LLMProvider`; telemetry goes through `Telemetry`.
- No autonomous data retrieval or vector search in v1.
- Typical latency target: p50 under 30 seconds and p95 under 75 seconds.
- Quality threshold: score >= 82 and no hard-fail flags.
- Output must be explainable enough for a human marketer or RevOps user to approve before activation.

## 8. ROI Analysis

Assumptions:

- Segmentation exercises: 10 per month.
- Current manual effort: 6 hours per campaign.
- Target effort with agent: 2.5 hours including review.
- Time saved: 3.5 hours per campaign.
- Loaded marketing operations cost: Rs 1,200/hour.
- Build cost using existing platform patterns: Rs 120,000.
- Annual hosting, monitoring, and maintenance: Rs 60,000.
- Inference estimate: Rs 20/request, 120 requests/year = Rs 2,400/year.

Annual value:

- Time savings: 10 x 12 x 3.5 x Rs 1,200 = Rs 504,000.
- Rework and campaign-waste reduction: Rs 200,000/year.
- Total estimated annual value: Rs 704,000.

Cost and ROI:

- Annual run cost: Rs 62,400.
- ROI = (Rs 704,000 - Rs 62,400) / (Rs 120,000 + Rs 62,400) = about 352%.
- Estimated payback: about 2.2 months.

## 9. Efficiency Targets

| Metric | Baseline today | Target with Agent 09 | Actual after launch |
|---|---:|---:|---|
| Segment strategy time | 4-8 hours | 45-120 minutes | TBD |
| Segment rule documentation | Inconsistent | 95%+ required rules present | TBD |
| Segment overlap detection | Manual | 90%+ overlap risks flagged | TBD |
| Suppression/compliance review prep | Manual | Standard warnings generated | TBD |
| Handoff readiness | Ad hoc | Structured handoff available | TBD |

## 10. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved demand generation, marketing operations, RevOps, and product marketing users |
| Runtime identity | Dedicated per-agent identity |
| Reads | User-submitted ICP, audience fields, campaign context, and direct-context performance summaries |
| Writes | Structured segmentation package, quality/cost metrics, redacted logs, optional provider-neutral artifact reference |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before any future CRM, MAP, ad-platform, or audience-list write |
| Audit | Segment count, risk flags, quality score, provider, cost, and status through `Telemetry` |

## 11. Security Considerations

- Audience data may contain PII, account intelligence, lifecycle status, and consent information.
- The agent must not segment by protected classes or sensitive personal traits.
- Consent, suppression, and regional restrictions must be preserved as hard constraints.
- Source data is untrusted content and cannot override platform instructions.
- No raw lead/account records should be logged.
- No external audience upload or CRM/MAP mutation in v1.

## 12. Cost Expectations

- Typical target: under Rs 15-20 per segmentation request.
- Hard ceiling: Rs 30/request in v1 config.
- Cost tracked per billable stage and emitted through `Telemetry`.
- If the cost ceiling would be exceeded, return safe partial segmentation with `stopped_cost_ceiling`.

## 13. Success Metrics

- 90%+ of complete-input eval cases produce 3-6 usable segments.
- 90%+ of generated segments include inclusion, exclusion, rationale, and messaging guidance.
- 95%+ of overlap or thin-segment risks are flagged in eval cases.
- 100% of protected-attribute segmentation requests are blocked or hard-flagged.
- 100% of eval runs stay under cost ceiling.

## 14. Evaluation Criteria

Eval cases should include:

- ICP package from Agent 08 with a standard campaign goal.
- Sparse audience fields with insufficient segmentation data.
- Highly overlapping candidate segments.
- Regional consent/suppression constraints.
- Mid-market versus enterprise segmentation.
- Prompt injection inside pasted audience notes.
- Protected-attribute segmentation request.

Pass criteria:

- Overall score >= 82.
- Segment-rule completeness >= 90%.
- Protected-attribute safety = 100%.
- Schema validity = 100%.
- Cost ceiling adherence = 100%.

## 15. Risks and Limitations

- Segmentation quality depends on supplied data quality and field availability.
- Over-segmentation can create campaign complexity without meaningful lift.
- Under-segmentation can hide important buyer differences.
- The agent cannot verify actual audience sizes without live system access in v1.
- It does not upload, suppress, or activate audience lists.
- Human review is required before campaign execution.

