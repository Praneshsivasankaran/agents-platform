# Agent 10 - Lead Generation Agent

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-10-lead-generation/`
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
deterministic domain logic unique to this agent today is capture-path and landing-page/form blueprint planning, with contact-list generation and purchased-list requests refused.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Use Case

Agent 10 creates a review-ready lead generation campaign blueprint from an ICP, audience segments, offer, channel constraints, and business goals. It recommends lead generation motions such as webinar, gated asset, outbound support, landing page brief, event follow-up, partner campaign, or paid acquisition concept; defines capture mechanics, qualification questions, conversion path, experiment plan, and downstream handoff fields for scoring and nurture.

V1 plans lead generation. It does not scrape contacts, buy lists, enrich leads, send outreach, publish landing pages, or activate campaigns.

## 2. Business Problem

Lead generation work often starts with fragmented briefs and moves straight into execution before the offer, audience, conversion path, and qualification logic are clear. This creates low-quality leads and expensive rework between demand generation, marketing operations, sales, and content teams. Agent 10 creates a structured campaign blueprint that can be reviewed before spend or implementation begins.

## 3. User Personas

- Demand generation manager designing a new campaign.
- Growth marketer selecting lead capture offers and channels.
- Marketing operations manager preparing form and routing requirements.
- SDR leader reviewing qualification and sales follow-up expectations.
- Content marketer planning lead magnets with campaign intent.

## 4. Inputs

- Agent 08 ICP package and/or Agent 09 segmentation package.
- Campaign goal, offer concept, product/service, target region, and funnel stage.
- Budget range, timeline, channel preferences, and constraints.
- Existing assets, content topics, landing page requirements, and CTA goals.
- Lead qualification criteria and sales follow-up expectations.
- Compliance, consent, and brand constraints.
- Past campaign performance summaries supplied as direct context.

## 5. Outputs

- Lead generation campaign blueprint.
- Recommended campaign motion and rationale.
- Target audience and segment mapping.
- Offer and lead magnet recommendations.
- Landing page brief and form-field recommendations.
- Lead capture and consent requirements.
- Qualification questions and scoring handoff notes.
- Channel plan, experiment plan, KPI targets, and operational dependencies.
- Risks, missing inputs, quality score, terminal status, and cost metadata.

## 6. Functional Requirements

1. Accept ICP/segment inputs and campaign context as direct structured data.
2. Validate campaign readiness and required constraints.
3. Recommend one or more lead generation motions matched to audience and funnel stage.
4. Define offer, CTA, landing page, form, and qualification mechanics.
5. Produce channel guidance without activating channels.
6. Generate downstream handoff notes for lead scoring and nurturing.
7. Flag unrealistic budgets, weak offers, consent issues, and missing sales follow-up assumptions.
8. Return a structured package with pass/fail status, quality score, and cost usage.

## 7. Non Functional Requirements

- Cloud selection must be config-driven.
- Agent logic must not import cloud SDKs, ad-platform SDKs, CRM/MAP SDKs, enrichment SDKs, scraping libraries, direct model SDKs, or `litellm`.
- Model calls must use `LLMProvider`; telemetry must use `Telemetry`.
- No external writes, scraping, enrichment, or autonomous audience discovery in v1.
- Typical latency target: p50 under 40 seconds and p95 under 90 seconds.
- Quality threshold: score >= 82 and no hard-fail flags.
- Output must be operationally specific enough for MarketingIQ Studio and human review.

## 8. ROI Analysis

Assumptions:

- Lead generation campaign plans: 6 per month.
- Current manual planning effort: 8 hours per campaign.
- Target effort with agent: 2 hours including review.
- Time saved: 6 hours per campaign.
- Loaded demand generation cost: Rs 1,300/hour.
- Build cost using existing platform patterns: Rs 140,000.
- Annual hosting, monitoring, and maintenance: Rs 60,000.
- Inference estimate: Rs 30/request, 72 requests/year = Rs 2,160/year.

Annual value:

- Time savings: 6 x 12 x 6 x Rs 1,300 = Rs 561,600.
- Lead quality and campaign rework reduction: Rs 300,000/year.
- Total estimated annual value: Rs 861,600.

Cost and ROI:

- Annual run cost: Rs 62,160.
- ROI = (Rs 861,600 - Rs 62,160) / (Rs 140,000 + Rs 62,160) = about 395%.
- Estimated payback: about 2.1 months.

## 9. Efficiency Targets

| Metric | Baseline today | Target with Agent 10 | Actual after launch |
|---|---:|---:|---|
| Campaign blueprint creation | 6-10 hours | 60-150 minutes | TBD |
| Landing page/form brief preparation | 2-4 hours | 30-60 minutes | TBD |
| Qualification requirement clarity | Inconsistent | 90%+ required fields present | TBD |
| Rework before launch | High | 30%+ reduction | TBD |
| Downstream scoring/nurture handoff | Ad hoc | Structured handoff available | TBD |

## 10. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved demand generation, growth, marketing operations, and sales leadership users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-submitted ICP, segments, campaign goals, offer, constraints, and direct-context performance summaries |
| Writes | Structured lead generation blueprint, quality/cost metrics, redacted logs, optional provider-neutral artifact reference |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before any future landing page publish, audience upload, email send, CRM write, or ad activation |
| Audit | Request id, campaign motion, risk flags, provider, cost, score, and status through `Telemetry` |

## 11. Security Considerations

- Inputs may include confidential campaign strategy, audience data, budget, conversion goals, and PII.
- The agent must preserve consent and suppression constraints.
- Source notes are untrusted content and must not override system instructions.
- The agent must not generate deceptive offers, false urgency, unsupported claims, or non-compliant lead capture flows.
- No raw records, budgets, or user-provided sensitive context should appear in logs.
- V1 must not perform contact discovery, scraping, enrichment, or external activation.

## 12. Cost Expectations

- Typical target: under Rs 20-30 per blueprint.
- Hard ceiling: Rs 40/request in v1 config.
- Cost tracked per billable stage and emitted through `Telemetry`.
- If the ceiling would be exceeded, return safe partial planning with `stopped_cost_ceiling`.

## 13. Success Metrics

- 85%+ of complete-input eval cases produce a campaign blueprint with offer, channel, landing page, form, KPI, and handoff sections.
- 90%+ of qualification and scoring handoff fields are present for pass cases.
- 100% of eval runs avoid external activation and scraping behavior.
- 100% of consent/suppression constraints are preserved.
- 100% of eval runs stay under cost ceiling.

## 14. Evaluation Criteria

Eval cases should include:

- ICP and segment package for a B2B SaaS webinar campaign.
- Gated whitepaper campaign with weak offer.
- Paid lead generation with budget constraints.
- Event follow-up lead capture.
- Missing sales follow-up rules.
- Prompt injection inside pasted campaign notes.
- Request to scrape or buy contacts.

Pass criteria:

- Overall score >= 82.
- Funnel completeness >= 85.
- Consent/suppression preservation = 100%.
- No external activation/scraping behavior = 100%.
- Schema validity and cost adherence = 100%.

## 15. Risks and Limitations

- Output quality depends on clarity of ICP, offer, and campaign goal.
- The agent cannot verify live audience size, channel inventory, or cost-per-lead without external integrations.
- It may recommend an impractical campaign if budget and operational constraints are missing.
- It does not generate or validate real contact records.
- Human review is required before launch, spend, or lead capture activation.

