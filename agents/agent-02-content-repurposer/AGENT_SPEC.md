# Agent 02 - Content Repurposing Agent Spec

## Identity

- Agent ID: `agent-02-content-repurposer`
- Canonical graph module: `agent/workflow.py`
- Compatibility graph module: `agent/graph.py`
- Status: v1, review-ready only

Agent 02 turns approved long-form source content into a structured package of
platform-specific marketing drafts for human review. It reuses the Agent 01
platform pattern: LangGraph workflow state, `LLMProvider` model calls, typed
Pydantic/CoreContractModel contracts, central cost authorization, telemetry,
guardrails, and offline evals.

## Users And Job

Primary users are marketers, content strategists, and campaign reviewers who
already have a source article or a serialized passed Agent 01 blog package and
need native drafts for multiple channels.

The agent should produce useful drafts that preserve the source meaning, adapt
to each channel, and remain easy for a human to approve, edit, or reject. It
must not publish, schedule, upload, email, or write to any external platform.

## Inputs

Agent 02 accepts a serialized contract only. It does not import Agent 01 code.

Required source fields:

- `source_type`: `agent01_blog_package` or `raw_article_text`
- one of `full_text`, `blog_body`, `summary`, or `title`

Supported optional source fields:

- `source_status`
- `human_approved`
- `seo_keywords`
- `suggested_tags`
- `meta_description`
- `source_metadata`

Campaign fields:

- `target_platforms`
- `include_newsletter`
- `audience`
- `brand_tone`
- `campaign_goal`
- `cta`

Default platforms are LinkedIn, Instagram, X/Twitter, and short-video script.
Newsletter/email is optional.

## Outputs

The terminal output is `RepurposedContentPackage`:

- terminal `status`
- source summary and content brief
- platform drafts
- markdown review package
- validation reports
- factual consistency report
- usefulness report
- quality report
- CTA options and hashtag sets
- cost ledger
- hard-fail list
- best-effort `output_package_uri` when configured storage succeeds

Inline output is always returned. Object storage is best-effort and must never
block local/test output.

## Terminal Statuses

- `pass`: review-ready package, quality score >= 85, no hard-fails
- `needs_more_input`: source is too thin or incomplete
- `needs_human`: terminal hard-fail or quality gate not recovered by revision
- `stopped_cost_ceiling`: Rs.30/package ceiling would be exceeded
- `error`: sanitized unexpected failure

## Quality Bar

Content quality is the main success metric.

Pass requires:

- overall quality score >= 85/100
- factual consistency score >= 90 in eval pass cases
- platform fit >= 85 in eval pass cases
- usefulness >= 85 in eval pass cases
- CTA clarity >= 85 in eval pass cases
- no hard-fails
- platform-native drafts that are not generic rewrites

Generic copy, weak hooks, weak CTAs, repetitive cross-platform reuse, unsupported
claims, fake facts, and changed meaning must not pass.

## Cost Ceiling

The hard v1 ceiling is Rs.30/package. Billable stages authorize before model
calls through `core.cost.authorize_call`. If a provider may have billed before a
failure, `BillableNodeError` preserves the incurred cost in the final ledger.

## V1 Out Of Scope

Agent 02 v1 must not perform:

- publishing or scheduling
- social posting
- CMS writes
- CRM writes
- ad platform actions
- email sends
- web search
- scraping
- irreversible external writes
- visual video analysis
- vector retrieval

## Cloud Neutrality

Inside `agent/`, there must be no direct cloud SDK imports and no direct model
SDK imports. Model calls go through `LLMProvider`; storage goes through
`ObjectStorage`; secrets go through `SecretStore`; telemetry goes through
`Telemetry`. Provider selection happens through config overlays.
