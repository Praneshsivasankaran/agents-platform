# Agent 03 - Content Ideation Agent Spec

## Identity

- Agent ID: `agent-03-content-ideation`
- Canonical graph module: `agent/workflow.py`
- Compatibility graph module: `agent/graph.py`
- Status: v1, review-ready strategy package only

Agent 03 turns campaign and marketing context into a structured Content
Ideation Package that can be reviewed by a human and passed to downstream
agents. It does not import Agent 01 or Agent 02 code. It only produces handoff
contracts for them.

## Users And Job

Primary users are marketers, content strategists, campaign managers, and
internal workflow orchestrators who need useful campaign ideas before writing or
repurposing content.

The agent should reduce vague campaign notes into clear themes, ideas, hooks,
CTAs, and downstream briefs. It must not write a finished blog, repurpose a
full source asset, publish, scrape, search the web, schedule content, or call
external marketing platforms.

## Inputs

Required fields:

- `campaign_goal`
- `product_or_service`
- `target_audience`
- `industry`
- `brand_tone`
- `key_message`
- `number_of_ideas`

Optional fields:

- `optional_notes`
- `optional_keywords`
- `optional_content_type_preference`
- `optional_constraints`

## Outputs

The terminal output is `ContentIdeationPackage`:

- terminal `status`
- campaign summary
- audience insights
- content themes
- ranked content ideas
- hooks
- CTA suggestions
- recommended formats
- quality score, quality notes, and risk flags
- `blog_brief_for_agent_01`
- `repurposing_brief_for_agent_02`
- recommended next agent
- cost ledger

## Terminal Statuses

- `pass`: review-ready package, quality score >= 80, no hard-fails
- `needs_more_input`: required or minimum campaign context is missing
- `needs_human`: terminal hard-fail or non-passing quality gate
- `stopped_cost_ceiling`: Rs.20/package ceiling would be exceeded
- `error`: sanitized unexpected failure

## Quality Bar

Pass requires:

- overall quality score >= 80/100
- no hard-fails
- at least one usable content idea
- Blog Brief for Agent 01 exists
- Repurposing Brief for Agent 02 exists
- risk flags are surfaced for human review

Scoring weights:

- relevance to campaign goal: 25
- audience fit: 20
- specificity: 15
- downstream usability: 15
- originality: 10
- brand fit: 10
- risk handling: 5

## V1 Out Of Scope

Agent 03 v1 must not perform:

- publishing, scheduling, CMS writes, CRM writes, or social posting
- web search, scraping, trend research, SEO keyword tools, or analytics calls
- image or video generation
- visual video analysis
- vector retrieval
- direct calls into Agent 01 or Agent 02 code

## Cloud Neutrality

Inside `agent/`, there must be no direct cloud SDK imports and no direct model
SDK imports. Model calls go through `LLMProvider`. Provider selection happens
through config overlays. GCP/Vertex is the first real target; Bedrock and Azure
remain behind the same provider interface.
