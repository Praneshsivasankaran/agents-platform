# Agent 15 - Keyword Research Agent Design

## 1. Metadata

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-15-keyword-research/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 15 converts supplied product, audience, campaign, seed keyword, and keyword metric context into a review-ready keyword strategy package. It must be evidence-aware, metric-honest, cloud-neutral, and useful as structured input for ad copy, landing page, paid optimization, multi-channel planning, and reporting.

## 3. Agent Boundaries

In scope:

- Cluster supplied keywords and seed topics.
- Classify likely search intent and funnel stage.
- Prioritize keywords using supplied metrics and clearly marked heuristics.
- Suggest negative keywords, ad groups, landing page mapping, and content angles.
- Produce missing-data warnings and downstream handoffs.

Out of scope:

- Live SEO tool calls, Search Console reads, rank checks, SERP crawling, website crawling, keyword scraping, external web research, or ranking guarantees.
- CMS, ad platform, analytics, CRM, or MAP writes.
- Autonomous purchase of keywords or budget changes.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_keyword_context
3. validate_required_context
4. parse_supplied_keyword_metrics
5. classify_intent_and_funnel_stage
6. generate_keyword_clusters
7. prioritize_keywords_and_negatives
8. map_clusters_to_pages_and_ad_groups
9. detect_metric_gaps_and_forbidden_requests
10. score_keyword_strategy
11. assemble_keyword_research_package
12. finalize_response
```

V1 should separate deterministic local checks from LLM-assisted reasoning. Metric parsing, missing-column detection, forbidden-action detection, duplicate term normalization, and status mapping are deterministic. Intent classification, cluster naming, and recommendation rationale may be LLM-assisted and validated deterministically.

## 5. State Model

Request-scoped state should contain:

- request metadata and normalized campaign context
- supplied keyword rows and metric column inventory
- missing metric report
- intent and funnel-stage classifications
- keyword clusters and priority candidates
- negative keyword suggestions
- page/ad group mapping
- evidence and assumptions
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain provider SDK objects, Search Console clients, browser objects, or live tool handles.

## 6. Inputs

Primary input concepts:

- product/service and offer
- ICP or audience segment summary
- campaign or content goal
- seed terms and keyword rows
- optional supplied keyword metrics
- competitor notes supplied by the user
- geography, language, funnel stage, landing page inventory, and exclusions
- upstream handoffs from Agents 08, 09, and 12

All inputs are direct context. There is no external fetch in v1.

## 7. Outputs

Primary output concepts:

- `KeywordResearchPackage`
- `KeywordCluster`
- `KeywordIntentClassification`
- `FunnelStageMapping`
- `PriorityKeyword`
- `NegativeKeywordRecommendation`
- `PageOrAdGroupMapping`
- `MissingMetricWarning`
- `EvidenceItem`
- `DigitalMarketingHandoff`
- `RiskFlag`
- `QualityReport`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `KeywordResearchRequest`
- `SuppliedKeywordRow`
- `KeywordMetricAvailability`
- `KeywordCluster`
- `IntentClassification`
- `PriorityRationale`
- `NegativeKeyword`
- `LandingPageMapping`
- `KeywordResearchQualityReport`
- `KeywordResearchPackage`

Shared status, risk, evidence, cost, and handoff models should be reused if a shared `packages/digital_marketing` package is created.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `normalize_keyword_terms` | raw keyword rows | normalized terms and duplicate groups | None | Local only |
| `detect_metric_columns` | supplied table | available/missing metric inventory | None | Local only |
| `validate_metric_claims` | output plus supplied metrics | fabricated metric flags | None | Local only |
| `detect_forbidden_keyword_actions` | request text | scraping/tool/rank-check hard-fail flags | None | Local only |
| `score_keyword_strategy` | clusters, mappings, risks | quality report | None | Local only |
| `estimate_cost_usage` | provider usage metadata | cost ledger | None | Local only |

No live SEO, Search Console, browser, SERP, ad platform, analytics, CRM, MAP, or CMS tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No vector retrieval, long-term keyword memory, or autonomous competitor memory in v1.
- Prior keyword plans may be supplied directly by the user as context.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require product/service, goal, audience/ICP context, and seed terms or supplied keyword rows.
- Flag missing volume, CPC, difficulty, rank, conversion, or spend data instead of inventing it.
- Reject or hard-flag scraping, crawling, Search Console access, SEO tool access, rank checks, and ranking guarantees.
- Hard-flag protected or sensitive targeting.
- Ensure every priority keyword has either supplied evidence or a heuristic label.
- Ensure downstream handoffs include assumptions and missing-data notes.

## 12. Quality Scoring Strategy

Agent 15 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Input normalization and metric honesty | 15 |
| Keyword cluster quality | 20 |
| Intent and funnel-stage classification | 15 |
| Priority rationale and evidence use | 15 |
| Negative keyword and exclusion usefulness | 10 |
| Page/ad group/content mapping | 10 |
| Risk and policy handling | 10 |
| Downstream handoff readiness | 5 |

Pass if score >= 82 and no hard-fail risk.

## 13. Evaluation Strategy

Eval datasets should cover complete keyword rows, sparse seed terms, supplied CPC/volume data, competitor notes without ranking data, protected targeting, scraping requests, prompt injection, and ranking-guarantee requests.

CI gates:

- schema_valid = 100%
- no_metric_fabrication = 100%
- forbidden_live_lookup_behavior = 100%
- protected_targeting_safety = 100%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 14. Error Handling Strategy

- Missing required context returns `needs_human` with required-field guidance.
- Cost guard failure returns `stopped_cost_ceiling` with safe partial normalization if available.
- Forbidden live lookup or ranking guarantee requests return hard-fail risk flags.
- Provider failure returns `error` with a redacted category and preserved cost usage.
- Malformed keyword tables return `needs_human` unless enough terms can be safely parsed.

## 15. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for intake, metric parsing, clustering, mapping, scoring, and finalization
- token and cost metrics by stage
- keyword count, cluster count, missing metric count, hard-fail count, quality score
- no raw strategy tables, budgets, account data, PII, or pasted notes in logs

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
- Optional persistence only through `ObjectStorage`.
- Secrets through `SecretStore`.
- Observability through `Telemetry`.
- No `google.cloud`, `vertexai`, `boto3`, `botocore`, Azure SDK, SEO tool SDK, Search Console SDK, browser automation SDK, direct model SDK, or `litellm` import inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents; Bedrock and Azure remain config/stub compatible.
- If shared logic lives in `packages/digital_marketing`, that package must receive its own no-cloud-SDK test.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render keyword clusters as editable strategy objects. The Digital Marketing tab should show intent mix, funnel-stage map, missing metric warnings, risk flags, quality score, and handoff buttons to Agents 16, 17, 18, 19, and 21.

## 19. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine with an Agent 15 profile. The profile should define required fields, forbidden SEO actions, missing-metric rules, quality dimensions, output sections, and eval cases. Future versions may add deeper deterministic tools for table parsing, keyword similarity, and local clustering if usage proves the need.
