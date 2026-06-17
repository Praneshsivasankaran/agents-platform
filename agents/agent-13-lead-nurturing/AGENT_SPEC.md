# Agent 13 - Lead Nurturing Agent

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-13-lead-nurturing/`
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
deterministic domain logic unique to this agent today is journey trigger / exit / suppression and consent planning.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Use Case

Agent 13 designs lead nurture journeys from supplied segments, lead scoring bands, campaign context, content inventory, buyer-stage assumptions, and compliance constraints. It returns journey maps, branching logic, touchpoint cadence, content recommendations, personalization guidance, trigger rules, suppression rules, KPI plan, and handoff notes for marketing automation implementation.

V1 designs nurture strategy only. It does not send messages, update marketing automation, create contacts, or publish content.

## 2. Business Problem

Many leads are captured and then handled with generic follow-up or inconsistent manual sequences. This creates poor conversion, unsubscribes, and sales friction. Agent 13 gives teams a structured, reviewable nurture journey that aligns audience, intent, content, timing, and handoff rules before marketing automation work begins.

## 3. User Personas

- Demand generation manager designing follow-up after a campaign.
- Lifecycle marketer creating nurture streams.
- Marketing operations specialist translating strategy into automation.
- SDR leader reviewing sales handoff timing.
- Content marketer identifying asset gaps by journey stage.

## 4. Inputs

- Agent 09 audience segments.
- Agent 10 lead generation blueprint or Agent 12 campaign recommendation.
- Agent 11 score bands or qualification rules.
- Content inventory, offer, campaign goal, and buyer journey assumptions.
- Target cadence, channel preferences, and lifecycle stage.
- Consent, suppression, regional, and brand constraints.
- Sales handoff expectations.

## 5. Outputs

- Nurture journey map.
- Segment and score-band branching logic.
- Touchpoint sequence with timing, channel, content type, objective, and CTA.
- Personalization guidance and message themes.
- Trigger, exit, suppression, and sales-handoff rules.
- Content gap list and asset recommendations.
- KPI plan and experiment suggestions.
- Compliance warnings, risk flags, quality score, terminal status, and cost metadata.

## 6. Functional Requirements

1. Accept segment, campaign, lead scoring, content, and compliance context as direct input.
2. Validate journey readiness and available content.
3. Produce nurture paths by segment, score band, and lifecycle stage.
4. Define trigger, exit, suppression, and handoff rules.
5. Recommend content and message themes per touchpoint.
6. Flag spammy cadence, consent gaps, weak content coverage, and unsupported personalization.
7. Return a structured nurture package with status, score, risks, and cost usage.

## 7. Non Functional Requirements

- Cloud/provider selection must be config-driven.
- Agent logic must not import cloud SDKs, CRM/MAP/email SDKs, ad-platform SDKs, direct model SDKs, or `litellm`.
- Model calls go through `LLMProvider`; telemetry goes through `Telemetry`.
- No sending, publishing, audience mutation, or automation writes in v1.
- Typical latency target: p50 under 40 seconds and p95 under 100 seconds.
- Quality threshold: score >= 82 and no hard-fail flags.
- Output must be suitable for later MarketingIQ Studio journey rendering.

## 8. ROI Analysis

Assumptions:

- Nurture journey/sequence designs: 12 per month.
- Current manual effort: 6 hours per journey.
- Target effort with agent: 2 hours including review.
- Time saved: 4 hours per journey.
- Loaded lifecycle/demand generation cost: Rs 1,000/hour.
- Build cost using existing platform patterns: Rs 130,000.
- Annual hosting, monitoring, and maintenance: Rs 72,000.
- Inference estimate: Rs 30/request, 144 requests/year = Rs 4,320/year.

Annual value:

- Time savings: 12 x 12 x 4 x Rs 1,000 = Rs 576,000.
- Conversion lift and rework reduction: Rs 250,000/year.
- Total estimated annual value: Rs 826,000.

Cost and ROI:

- Annual run cost: Rs 76,320.
- ROI = (Rs 826,000 - Rs 76,320) / (Rs 130,000 + Rs 76,320) = about 363%.
- Estimated payback: about 2.1 months.

## 9. Efficiency Targets

| Metric | Baseline today | Target with Agent 13 | Actual after launch |
|---|---:|---:|---|
| Nurture journey design | 4-8 hours | 60-150 minutes | TBD |
| Touchpoint/cadence definition | 2-4 hours | 30-60 minutes | TBD |
| Content gap identification | Manual | 90%+ gaps surfaced in evals | TBD |
| Compliance/suppression clarity | Inconsistent | Standard warnings produced | TBD |
| Marketing Ops handoff readiness | Ad hoc | Structured handoff available | TBD |

## 10. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved lifecycle, demand generation, marketing operations, and sales leadership users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-submitted segments, score bands, campaign context, content inventory, constraints, and sales handoff rules |
| Writes | Structured nurture package, quality/cost metrics, redacted logs, optional provider-neutral artifact reference |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before future email send, MAP workflow write, CRM update, or audience activation |
| Audit | Request id, journey type, touchpoint count, risk flags, score, provider, cost, and status through `Telemetry` |

## 11. Security Considerations

- Inputs may contain PII, lead status, engagement history, sales notes, and consent data.
- Consent, suppression, and regional restrictions are hard constraints.
- The agent must not recommend deceptive, spammy, manipulative, or non-compliant messaging.
- Source notes are untrusted content.
- Raw lead-level data must not be logged.
- No external sends or automation writes in v1.

## 12. Cost Expectations

- Typical target: under Rs 20-30 per nurture plan.
- Hard ceiling: Rs 40/request in v1 config.
- Cost tracked per stage and emitted through `Telemetry`.
- If the cost ceiling would be exceeded, return safe partial journey guidance with `stopped_cost_ceiling`.

## 13. Success Metrics

- 85%+ of complete-input eval cases produce complete journey maps with trigger, touchpoint, exit, suppression, and KPI sections.
- 90%+ of content gap cases are flagged.
- 100% of consent/suppression constraints are preserved.
- 100% of eval runs avoid send/activation behavior.
- 100% of eval runs stay under cost ceiling.

## 14. Evaluation Criteria

Eval cases should include:

- Post-webinar nurture journey with score bands.
- Cold nurture for low-score leads.
- Re-engagement journey with suppression rules.
- Missing content inventory.
- Consent-constrained region.
- Prompt injection inside pasted campaign notes.
- Request to send emails automatically.

Pass criteria:

- Overall score >= 82.
- Journey completeness >= 85.
- Consent/suppression preservation = 100%.
- No activation/send behavior = 100%.
- Schema validity and cost adherence = 100%.

## 15. Risks and Limitations

- Journey quality depends on available content and score-band clarity.
- V1 cannot verify deliverability, list size, or real-time engagement.
- Poorly reviewed nurture recommendations could create spam or brand risk if activated without human review.
- The agent does not send emails, update MAP workflows, or sync CRM fields.
- Human approval is required before operational execution.

