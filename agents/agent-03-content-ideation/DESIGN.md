# Agent 03 - Content Ideation Agent Design

## Reference Pattern

Agent 03 follows the Agent 01 and Agent 02 platform pattern:

- LangGraph for workflow topology and terminal routing
- LiteLLM through shared `LLMProvider`
- `CoreContractModel` schemas for strict immutable contracts
- central `core.cost` authorization and usage ledger
- telemetry through `Telemetry`
- no direct cloud SDK imports inside `agent/`
- no direct imports of Agent 01 or Agent 02 implementation code

## Workflow

Canonical workflow:

```text
intake
-> validate_campaign_brief
-> analyze_audience
-> generate_content_themes
-> generate_content_ideas
-> generate_hooks
-> create_blog_brief_for_agent_01
-> create_repurposing_brief_for_agent_02
-> quality_scoring
-> assemble_content_ideation_package
```

The graph always funnels into `assemble_content_ideation_package`, so invalid
input, cost ceiling stops, provider hiccups, and unexpected errors return a
typed terminal package.

## State

`Agent03State` contains the serialized input, validated request, campaign
summary, audience insights, content themes, content ideas, hooks, CTA
suggestions, downstream briefs, quality report, cost ledger, hard-fails,
terminal status, and final output.

`cost_usage` and `hard_fails` use LangGraph reducers with `operator.add`.

## Contracts

All terminal and provider-facing contracts live in `agent/contracts.py`.
Compatibility imports are provided through `agent/schemas.py`.

Important contracts:

- `ContentIdeationRequest`
- `CampaignSummary`
- `AudienceInsights`
- `ContentTheme`
- `ContentIdea`
- `LLMIdeaBundle`
- `CtaSuggestion`
- `BlogBriefForAgent01`
- `RepurposingBriefForAgent02`
- `QualityReport`
- `CostUsage`
- `ContentIdeationPackage`

## Model Use

The `generate_content_ideas` stage asks `LLMProvider` for a structured
`LLMIdeaBundle`. The deterministic idea generator is the fallback and the
quality gate remains the source of truth. The `quality_scoring` stage may call
the model for review context, but deterministic scoring decides pass/fail.

All billable calls run through `core.cost.authorize_call` before the provider
is called.

## Quality Gate

The quality gate checks:

- required output fields are present
- at least one usable idea exists
- ideas are not duplicates
- ideas are specific enough for the audience
- Blog Brief and Repurposing Brief exist
- unsupported numerical claims are flagged
- live research or scraping requests are rejected
- quality score reaches 80

Terminal hard-fails route to `needs_human`. Missing required input routes to
`needs_more_input`. Warning risk flags can remain on a passing package.

## Security And Scope

V1 is review-ready only. Agent 03 does not publish, schedule, scrape, search,
write to external systems, or fetch third-party marketing data. Optional notes
are placed behind prompt trust boundaries and treated as data, never as
instructions.

## Config

`config/base.yaml` is the offline mock config with a Rs.20/package ceiling.
`config/gcp.yaml`, `config/bedrock.yaml`, and `config/azure.yaml` preserve the
same provider-selected shape. GCP is the first real target; AWS and Azure remain
stubbed behind the same abstractions.

## Eval Plan

The offline eval suite covers:

- B2B SaaS awareness
- product launch
- event promotion
- customer education
- social-first campaign
- unsupported metric request
- missing required input

Checks validate schema, terminal status, quality threshold, risk handling,
cost ceiling, and the Agent 01/Agent 02 handoff contracts.
