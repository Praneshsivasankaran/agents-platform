# Agent 08 - ICP Identification Agent

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Demand Generation
**Agent path:** `agents/agent-08-icp-identification/`
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
deterministic domain logic unique to this agent today is evidence-backed ICP fit signals and disqualifier flagging.

Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

---

## 1. Use Case

Agent 08 helps a demand generation team identify and document enterprise Ideal Customer Profiles (ICPs) from user-provided product context, customer evidence, win/loss notes, market constraints, and sales knowledge. The agent converts messy GTM inputs into ranked ICP profiles with firmographic criteria, buying triggers, disqualifiers, pains, buying committee guidance, evidence strength, confidence levels, and downstream handoff notes for segmentation, campaign planning, lead scoring, and nurture design.

V1 is advisory and planning-only. It does not enrich accounts, scrape the web, buy contact data, update CRM records, or automatically activate campaigns.

## 2. Business Problem

Many B2B teams waste media spend and sales effort because their ICP is either too broad, based on anecdotes, or buried across decks, CRM exports, founder notes, and sales conversations. Without a clear ICP, audience segmentation, lead generation, scoring, and nurture flows inherit weak assumptions. Agent 08 creates a reusable, evidence-aware ICP definition that can become the first Demand Generation building block.

## 3. User Personas

- Head of Demand Generation defining target accounts for a campaign cycle.
- Product marketer translating positioning into market-fit criteria.
- Sales leader aligning SDR/account targeting with real win patterns.
- RevOps analyst standardizing fit criteria before scoring or routing.
- Founder/operator preparing the first enterprise GTM motion.

## 4. Inputs

- Product or service description.
- Target market, geography, industry, company-size, and revenue constraints.
- Current customer summaries, CRM export summaries, or account notes supplied by the user.
- Win/loss notes, sales call summaries, objection themes, and competitive context.
- Best-fit and poor-fit customer examples.
- Use cases, pain points, value propositions, pricing/packaging constraints, and implementation requirements.
- Existing ICP/persona documents, if any.
- Compliance, exclusion, or data-residency constraints.

## 5. Outputs

- Ranked ICP profiles with names, descriptions, and confidence levels.
- Firmographic, technographic, operational, and trigger-event criteria.
- Positive fit signals, negative fit signals, and disqualifiers.
- Buying committee map with economic buyer, champion, blocker, and influencer roles.
- Pain points, value propositions, objections, and proof needs per ICP.
- Evidence map showing which source inputs support each recommendation.
- Targeting guardrails, account-selection rules, and handoff notes for Agents 09, 10, 11, 12, and 13.
- Missing-information warnings, risk flags, quality score, final status, and cost metadata.

## 6. Functional Requirements

1. Accept structured fields and pasted source notes as direct context.
2. Normalize product, market, customer, and sales-evidence inputs.
3. Detect whether the supplied evidence is sufficient to produce an ICP.
4. Identify candidate ICP clusters and merge duplicates.
5. Produce ranked ICP profiles with fit criteria and disqualifiers.
6. Separate evidence-backed claims from assumptions.
7. Flag weak evidence, overbroad markets, protected-attribute risks, and unsupported targeting claims.
8. Generate downstream handoff guidance for segmentation and scoring.
9. Return a structured package with a terminal status of `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`.

## 7. Non Functional Requirements

- Cloud selection must happen by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, CRM SDKs, or enrichment SDKs inside `agent/`.
- Model calls must go through `LLMProvider`; storage, secrets, and telemetry must go through platform abstractions.
- V1 uses request-scoped state only; no vector retrieval or long-term account memory.
- Typical latency target: p50 under 35 seconds and p95 under 90 seconds for normal text/structured requests.
- Output must be schema-valid, explainable, and usable for human review.
- Quality threshold: score >= 82 and no hard-fail conditions.

## 8. ROI Analysis

Assumptions:

- ICP refresh or new-market analysis: 4 per month.
- Current manual effort: 8 hours per ICP exercise.
- Target effort with agent: 2 hours including human review.
- Time saved: 6 hours per exercise.
- Loaded GTM strategy cost: Rs 1,500/hour.
- Build cost using the existing scaffold: Rs 130,000.
- Annual hosting, monitoring, and maintenance: Rs 48,000.
- Inference estimate: Rs 25/request, 48 requests/year = Rs 1,200/year.

Annual value:

- Time savings: 4 x 12 x 6 x Rs 1,500 = Rs 432,000.
- Reduced campaign waste and targeting rework: Rs 150,000/year.
- Total estimated annual value: Rs 582,000.

Cost and ROI:

- Annual run cost: Rs 49,200.
- ROI = (Rs 582,000 - Rs 49,200) / (Rs 130,000 + Rs 49,200) = about 297%.
- Estimated payback: about 2.9 months.

## 9. Efficiency Targets

| Metric | Baseline today | Target with Agent 08 | Actual after launch |
|---|---:|---:|---|
| ICP strategy drafting time | 6-10 hours | 60-120 minutes | TBD |
| Source evidence review time | 3-5 hours | 45-90 minutes | TBD |
| Targeting criteria consistency | Inconsistent | 90%+ required fields present | TBD |
| Weak-assumption visibility | Manual | 95%+ weak assumptions flagged in evals | TBD |
| Downstream handoff readiness | Ad hoc | Structured handoff available | TBD |

## 10. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing, sales, RevOps, and product marketing users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-submitted product, customer, sales, and market context only |
| Writes | Structured ICP package, quality/cost metrics, redacted logs, optional provider-neutral artifact reference |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before any future CRM/account-list write or campaign activation |
| Audit | Request id, provider, cost, status, score, risk flags, and source types through `Telemetry` |

## 11. Security Considerations

- ICP inputs may contain confidential GTM strategy, customer names, revenue data, sales notes, and PII.
- Source notes are untrusted data and must never override system instructions.
- The agent must not infer or recommend targeting based on protected classes or sensitive personal attributes.
- Raw customer examples must not be logged.
- No external enrichment, scraping, CRM mutation, or data export in v1.
- Any future integration with CRM, data warehouse, enrichment, or ad platforms requires separate design review, least-privilege scopes, and HITL for writes.

## 12. Cost Expectations

- Typical target: under Rs 15-25 per ICP request.
- Hard ceiling: Rs 35/request in v1 config.
- Cost is tracked per stage and emitted through `Telemetry`.
- If the next billable stage cannot fit under the ceiling, the workflow must stop with `stopped_cost_ceiling` and return any safe partial analysis.

## 13. Success Metrics

- 90%+ of complete-input eval cases produce at least two distinct ICP profiles.
- 95%+ of output claims are tied to supplied evidence or marked as assumptions.
- 90%+ of downstream handoff fields are present for pass cases.
- 100% of protected-attribute targeting attempts are rejected or flagged.
- 100% of eval runs stay under the configured cost ceiling.
- Human reviewers rate ICP usefulness 4/5 or better after pilot.

## 14. Evaluation Criteria

Eval cases should include:

- Mature B2B SaaS with clear customer evidence.
- Early-stage company with sparse evidence.
- Enterprise services business with multiple possible segments.
- Overbroad "everyone is our customer" input.
- Conflicting win/loss signals.
- Prompt-injection text inside pasted notes.
- Protected-attribute or non-compliant targeting request.

Pass criteria:

- Overall quality score >= 82.
- Evidence discipline score >= 85.
- Protected-attribute safety = 100%.
- Schema validity = 100%.
- Cost ceiling adherence = 100%.

## 15. Risks and Limitations

- Weak or biased source data can produce misleading ICPs.
- Over-specific ICPs may reduce market opportunity if the user provides too little evidence.
- Revenue or fit signals from old customers may be stale.
- The agent cannot validate market size without external research in v1.
- It does not create account lists or contact records.
- It must remain advisory until a human approves targeting strategy.

