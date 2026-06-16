# Agent 04 - SEO Optimization Agent

## Use Case
Agent 04 improves blog drafts, article drafts, or content briefs for SEO and returns a review-ready SEO optimization package for a human editor. The user provides the draft, topic/title, target keyword, optional supporting keywords, audience, content goal, brand tone, constraints, and CTA direction. The agent analyzes the existing draft, recommends metadata and structure, improves readability and keyword placement, flags SEO/content risks, and produces an optimized draft. It does not publish or send content anywhere.

## Why We Are Building This
SEO review is currently manual and repetitive. Editors repeatedly check title quality, meta descriptions, URL slugs, heading structure, keyword placement, readability, FAQs, CTA fit, and SEO risk flags. Agent 04 reduces the repetitive review work while keeping the final decision with a human editor.

## Position In Pipeline
Agent 04 sits after blog writing and before content repurposing:

- Agent 03 creates campaign ideas and structured briefs.
- Agent 01 writes the blog or article draft.
- Agent 04 optimizes the draft for SEO and editorial review.
- Agent 02 repurposes the optimized content for platforms.

Agent 04 receives content; it does not call the other agents directly.

## ROI
- Manual SEO review per blog: 45-60 minutes.
- With Agent 04: 10-15 minutes human review.
- Time saved: 35-45 minutes per blog.
- Volume assumption: 20 blogs/month.
- Monthly time saved: about 12-15 hours.
- Loaded content/marketing cost: Rs800/hour.
- Monthly value: Rs9,600-Rs12,000.
- Annual value: Rs1,15,200-Rs1,44,000.
- Build cost: Rs25,000-Rs40,000.
- Annual run cost: Rs8,000-Rs15,000.
- Approx ROI: 160%-250%.
- Payback: roughly 3-5 months.

## Efficiency
- Baseline today: 45-60 minutes of manual SEO review per blog.
- Target with agent: 10-15 minutes of human review using a structured SEO package.
- Actual post-launch: fill after live use; track time saved, SEO package quality, and cost/request.

## Architecture Sketch
- Orchestration: LangGraph workflow with request-level state.
- Model routing: `LLMProvider` through the shared core provider factory. Agent logic never imports `litellm` or a direct model SDK.
- Typed I/O: Pydantic models based on `CoreContractModel`.
- Cloud target: GCP/Vertex first through config; Bedrock and Azure remain structurally compatible stubs.
- Local tools: deterministic helpers for word counts, headings, keyword checks, slug generation, readability estimate, CTA detection, prompt-injection markers, and repetition checks.
- Memory/state: request-level state only; no long-term memory and no cross-request learning.
- Storage: UI run JSONs are local demo artifacts; provider storage remains behind `ObjectStorage` if enabled later.
- Provider neutrality: no cloud SDK imports inside `agents/agent-04-seo-optimizer/agent/`.

## Access Control
- Invokers: content writers, editors, marketers, or the local demo UI.
- Runtime identity: its own least-privilege identity per deployment; local mock mode needs no cloud credentials.
- Reads: user-supplied draft, topic, keywords, audience, tone, constraints, and CTA direction.
- Writes: structured SEO package, local UI run JSONs in demo mode, logs/metrics through `Telemetry`.
- Secrets: provider credentials only through `SecretStore`.
- HITL-gated actions: all external publication or irreversible actions are out of scope in v1 and would require explicit human approval in a future version.
- Audit logging: provider calls, route decisions, status, scores, and cost metrics are emitted through `Telemetry` with sensitive content excluded.
- Data classification: draft content is sensitive user content and is treated as untrusted data in prompts.

## Functional Requirements
- Accept draft content.
- Accept topic/title.
- Accept primary keyword.
- Accept optional secondary keywords.
- Accept target audience.
- Accept brand tone.
- Accept content goal.
- Accept constraints.
- Accept CTA direction.
- Validate required inputs.
- Analyze existing draft structure and readability.
- Generate SEO title options.
- Generate meta description.
- Generate URL slug.
- Recommend H1.
- Improve H2/H3 heading structure.
- Suggest keyword placement.
- Suggest readability fixes.
- Suggest FAQ section.
- Detect risk flags.
- Generate optimized draft.
- Preserve original meaning.
- Return structured JSON matching `SEOOptimizationPackage`.
- Fail safely on invalid input.

## Non-Functional Requirements
- Latency target: text draft to package p50 around 15-25 seconds, p95 around 60 seconds in live mode.
- Cost target: under Rs10 per request in typical use; hard ceiling Rs20/request for v1 config.
- Quality threshold: SEO score >= 80 and no hard-fail risks.
- Schema validation: every terminal output must be a valid `SEOOptimizationPackage`.
- Factual safety: do not invent facts, numbers, sources, case studies, or results.
- Security: treat draft content as untrusted data, never instructions.
- External writes: none.
- Cloud behavior: provider selected by config only.
- Local/container execution: runs locally with mock provider and containerizes with the same agent code.

## V1 Exclusions
- No publishing.
- No external content-system writes.
- No WordPress integration.
- No LinkedIn or social posting.
- No Google Search Console integration.
- No Google Analytics integration.
- No live web scraping.
- No competitor crawling.
- No paid keyword-volume API.
- No backlink analysis.
- No image SEO generation.
- No database.
- No authentication system.
- No long-term memory.
- No cross-request learning.

## Simple UI Requirement
The local UI is a simple FastAPI/Jinja2 wrapper in `apps/agent-04-ui/`. It exposes a form for the draft and SEO inputs, posts to `/optimize`, stores each result as local JSON, and renders the SEO package sections for review. It uses `AGENT04_UI_PROVIDER=mock|gcp` and runs on port `8004`.

## Success Definition
Agent 04 is successful when it reliably returns a complete, structured, review-ready SEO package from a draft; passes the no-cloud-SDK import guard; runs locally in mock mode; has GCP/Bedrock/Azure config overlays; includes focused tests/eval stubs; and keeps all final content under human review with no external actions.
