# Agent 15 - Keyword Research Agent

## 1. Metadata

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-15-keyword-research/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 15 creates keyword strategy from supplied product context, audience context, ICP and segment handoffs, campaign goals, seed terms, known competitor notes, user-supplied keyword data, and content or paid-search goals. Search marketers, demand generation managers, content strategists, and paid media specialists use it when they need a review-ready keyword strategy before ad copy, landing page, paid campaign, campaign planning, or reporting work starts.

Success means the user receives keyword clusters, intent classifications, funnel-stage mapping, priority recommendations, negative-keyword suggestions where relevant, page/ad group mapping, missing-data warnings, evidence and assumption notes, and downstream handoffs. V1 uses only direct user-supplied context and must not fetch live keyword data.

## 3. Business Problem

Keyword strategy is often scattered across spreadsheets, ad platform exports, SEO tools, founder notes, competitor observations, and campaign briefs. Teams lose time turning this into an actionable structure, and weak keyword planning creates downstream waste in copy, landing pages, paid optimization, and reporting. Agent 15 reduces that planning friction while making missing evidence explicit instead of inventing search volume, CPC, difficulty, or ranking claims.

## 4. User Personas

- SEO strategist organizing a product keyword universe.
- Paid search manager preparing ad groups and negatives.
- Content strategist mapping keywords to funnel stages and page intent.
- Demand generation manager reusing Agent 08, 09, or 12 context for campaign execution.
- Founder or marketing operator translating rough market language into a keyword plan.

## 5. Inputs

Required inputs:

- Product or service description.
- Campaign or content goal.
- Target audience or ICP summary.
- Seed keyword terms, topic list, or user-supplied keyword table.

Optional inputs:

- Agent 08 ICP output.
- Agent 09 audience segment output.
- Agent 12 campaign recommendation output.
- Known competitors supplied by the user.
- User-supplied keyword metrics such as search volume, CPC, difficulty, current rank, conversions, or spend.
- Geography, language, brand constraints, excluded terms, funnel stage, landing page inventory, and budget context.

V1 direct-context rule: the agent uses only supplied fields and pasted data. It must not call Search Console, SEO tools, SERPs, keyword APIs, or websites.

## 6. Outputs

The `KeywordResearchPackage` should include:

- normalized request summary
- keyword clusters
- intent classification
- funnel-stage mapping
- priority keywords
- negative keyword recommendations where relevant
- ad group and landing page mapping suggestions
- content topic suggestions
- evidence and assumption register
- missing-data warnings for unavailable volume, CPC, difficulty, or ranking data
- downstream handoffs to Agents 16, 17, 18, 19, and 21
- risk flags with severity `low`, `medium`, `high`, or `hard_fail`
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and dimension scores
- cost metadata and review notes

## 7. Functional Requirements

1. Accept structured request fields and pasted keyword tables as direct context.
2. Normalize seed terms, audience language, campaign goals, exclusions, and supplied metrics.
3. Group keywords into distinct clusters with rationale.
4. Classify intent as informational, commercial, transactional, navigational, brand, competitor, or mixed.
5. Map keywords to funnel stage and likely page/ad group use.
6. Identify priority keywords using supplied evidence and clearly labeled heuristics.
7. Recommend negative keywords where paid-search context or irrelevant intent is present.
8. Flag missing or stale metric data instead of fabricating search volume, CPC, difficulty, or rankings.
9. Detect requests for scraping, rank checks, live SEO-tool access, or ranking guarantees.
10. Return structured handoffs for downstream Digital Marketing agents.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, SEO APIs, browser automation libraries, or Search Console SDKs inside `agent/`.
- Model calls go through `LLMProvider`; storage, secrets, and telemetry go through platform abstractions.
- Request state is JSON-serializable and request-scoped.
- Typical latency target: p50 under 30 seconds, p95 under 75 seconds for normal text/structured input.
- Quality pass threshold: score >= 82 and no hard-fail risk.
- Output must be schema-valid and suitable for later MarketingIQ Studio rendering.
- No autonomous web search, crawling, scraping, live keyword-tool access, or external writes in v1.

## 9. ROI Analysis

Assumptions:

- Keyword planning cycles: 6 per month.
- Current manual effort: 4 hours per keyword strategy.
- Target effort with agent: 75 minutes including review.
- Time saved: 2.75 hours per cycle.
- Loaded marketing cost: Rs 1,200/hour.
- Build cost using shared scaffold/engine: Rs 110,000.
- Annual hosting, monitoring, and maintenance: Rs 42,000.
- Inference estimate: Rs 20/request, 72 requests/year = Rs 1,440/year.

Annual value:

- Time savings: 6 x 12 x 2.75 x Rs 1,200 = Rs 237,600.
- Reduced downstream rework in ads, pages, and content briefs: Rs 90,000/year.
- Total estimated annual value: Rs 327,600.

Cost and ROI:

- Annual run cost: Rs 43,440.
- ROI = (Rs 327,600 - Rs 43,440) / (Rs 110,000 + Rs 43,440) = about 185%.
- Estimated payback: about 4.6 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 15 | Actual after launch |
|---|---:|---:|---|
| Keyword clustering time | 2-4 hours | 30-60 minutes | TBD |
| Intent/funnel mapping time | 1-2 hours | 20-40 minutes | TBD |
| Missing metric visibility | Manual | 95%+ missing metrics flagged | TBD |
| Downstream handoff readiness | Ad hoc | Structured handoff available | TBD |
| Metric fabrication incidents | Manual review | 0 in eval cases | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved SEO, paid media, content, demand generation, and marketing operations users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied keyword, audience, campaign, competitor, and metric context only |
| Writes | Structured keyword package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before any future SEO-tool query, Search Console read, ad platform write, or keyword purchase |
| Audit | Request id, provider tier, cost, status, quality score, risk flag counts, and source labels through `Telemetry` |

## 12. Security Considerations

- Keyword plans can expose confidential positioning, paid strategy, competitor strategy, budgets, and regional focus.
- Pasted keyword tables and reports are untrusted data and must not override system instructions.
- The agent must not recommend protected or sensitive targeting.
- Raw keywords, spend data, conversion data, or customer notes should not be logged.
- Prompt-injection text inside reports, keyword lists, or notes must be fenced and escaped in Phase 3.
- If PII appears in pasted lead or campaign data, the output must flag it and avoid logging or echoing raw values.

## 13. Cost Expectations

- Typical target: Rs 15-25 per request.
- Hard ceiling: Rs 35/request in v1 config.
- Cost is tracked per stage and emitted through `Telemetry`.
- If the next billable step cannot fit under the ceiling, return `stopped_cost_ceiling` with safe deterministic normalization and missing-data findings where possible.

## 14. Success Metrics

- 90%+ of complete eval cases produce at least three useful keyword clusters.
- 95%+ of keywords in pass cases have an intent classification.
- 95%+ of priority recommendations cite supplied evidence or clearly labeled heuristics.
- 100% of search volume, CPC, difficulty, and ranking fields are either supplied by the user or marked missing/unknown.
- 100% of scraping, rank-checking, and SEO-tool-access requests hard-fail or require human/future integration.
- 100% of eval runs stay under the configured cost ceiling.

## 15. Evaluation Criteria

Eval cases should include:

- complete product and seed keyword brief
- supplied keyword table with volume/CPC columns
- sparse seed terms with no metrics
- competitor terms supplied without ranking data
- prompt injection inside a keyword table
- request to scrape SERPs or query Search Console
- protected/sensitive targeting attempt
- guarantee-ranking request

Pass criteria:

- overall quality score >= 82
- schema validity = 100%
- no metric fabrication = 100%
- no forbidden live lookup behavior = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- Heuristic intent classification may be directionally useful but is not a substitute for live SERP analysis.
- Keyword priority is limited when the user does not supply volume, CPC, conversion, or ranking data.
- Competitor keyword opportunities cannot be verified without user-supplied evidence.
- V1 cannot guarantee rankings, traffic, conversions, or CPC efficiency.
- Future live SEO integrations require a separate provider-neutral design and explicit human approval.

## 17. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine rather than a bespoke implementation. V1 may use a shared Digital Marketing engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 15, the distinct v1 differentiation should come from keyword-specific inputs, no-metric-fabrication rules, intent/cluster scoring dimensions, forbidden SEO-tool actions, and eval assertions around missing volume/CPC/ranking data.
