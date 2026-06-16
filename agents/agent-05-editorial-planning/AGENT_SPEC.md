# Agent 05 - Editorial Planning Agent

## Use Case
Agent 05 creates a review-ready editorial calendar and content plan for a brand, campaign, or company. The user provides brand context, business goals, audience, campaign theme, platforms, date range, posting frequency, tone, content pillars, optional existing ideas, and optional constraints. The agent returns a structured planning package that helps a human decide what content to create, when it should be created, which platform it belongs on, and what brief should guide creation.

Agent 05 v1 is planning-only. It creates recommendations, briefs, gaps, risks, and review notes. It does not publish, schedule, write to calendars, call social APIs, or modify external systems.

## Why We Are Building This
Editorial planning is repetitive and easy to make inconsistent across channels. Teams need to balance campaign goals, content pillars, dates, platform fit, repurposing, CTAs, and production priority. Today this is often done manually in spreadsheets or documents, which leads to missing dates, uneven platform coverage, duplicate ideas, weak briefs, and unclear handoffs to writers or designers.

Agent 05 reduces that planning effort by generating a structured editorial package that a human can review, edit, and approve. It becomes the planning layer that can later feed writing, SEO, and repurposing agents without tightly coupling those agents together.

## Position In Pipeline
Agent 05 sits before content creation and optimization:

- Agent 03 can generate campaign ideas and high-level campaign briefs.
- Agent 05 turns brand/campaign inputs into an editorial calendar, platform plan, and content briefs.
- Agent 01 can use an approved Agent 05 brief to write blog/article content.
- Agent 04 can optimize written drafts for SEO.
- Agent 02 can repurpose approved content for platforms.

Agent 05 may accept optional ideas from Agent 03-style campaign outputs, but it does not call other agents directly in v1. It returns structured output that other tools or humans may use later.

## ROI
- Manual editorial planning for a campaign/month: 3-6 hours.
- With Agent 05: 45-90 minutes of human review and adjustment.
- Time saved per planning cycle: about 2-4.5 hours.
- Volume assumption: 4 planning cycles/month.
- Monthly time saved: about 8-18 hours.
- Loaded marketing/editorial cost: Rs800/hour.
- Monthly value: Rs6,400-Rs14,400.
- Annual value: Rs76,800-Rs1,72,800.
- Build cost: Rs25,000-Rs45,000.
- Annual run cost: Rs8,000-Rs18,000.
- Approx ROI: 120%-260%.
- Payback: roughly 3-6 months.

## Efficiency
- Baseline today: 3-6 hours of manual calendar planning per campaign/month.
- Target with agent: 45-90 minutes of human review using a structured planning package.
- Actual post-launch: fill after live use; track time saved, plan quality, human edit rate, and cost/request.

## V1 Scope
Agent 05 v1 produces planning artifacts only:

- editorial calendar
- weekly or monthly content plan
- platform-wise content plan
- content briefs
- suggested titles/topics
- content type recommendations
- content objective
- CTA suggestions
- priority
- due date recommendations
- repurposing map
- balance/gap analysis
- risk flags
- quality score
- review notes

The output is draft planning material for human review. Dates are planning dates, not scheduled posts.

## Inputs
Required inputs:

- brand/company name
- business goal
- target audience
- campaign theme
- platforms
- date range
- posting frequency
- tone/brand voice
- content pillars or themes

Optional inputs:

- existing ideas
- constraints
- priority platforms
- excluded topics
- key products/offers
- important dates
- approval lead time
- production capacity
- regional or language preferences

All user-provided inputs are treated as untrusted data in prompts. They may influence the plan but cannot override system safety, provider-neutrality, or v1 scope boundaries.

## Outputs
The terminal output is an `EditorialPlanningPackage` containing:

- normalized request summary
- editorial calendar entries
- weekly/monthly content plan
- platform-wise plan
- content briefs for each planned item
- suggested titles/topics
- content type
- objective
- CTA suggestions
- priority
- planned publish date
- internal due date
- repurposing map
- balance and gap analysis
- risk flags
- quality score and pass/fail status
- review notes
- cost summary
- terminal status

Output must be schema-valid JSON when invoked through the agent service or UI API.

## Architecture Sketch
- Orchestration: LangGraph workflow with request-level state.
- Model routing: `LLMProvider` through shared core provider wiring. Agent logic never imports `litellm` or a direct model SDK.
- Typed I/O: Pydantic models based on shared core contract conventions.
- Cloud target: GCP/Vertex first through config; Bedrock and Azure remain structurally compatible stubs.
- Local tools: deterministic helpers for date range validation, posting cadence expansion, platform normalization, topic deduplication, pillar balance checks, due-date calculation, priority ordering, and risk detection.
- Memory/state: request-level state only; no long-term memory and no cross-request learning.
- Storage: generated planning packages may be written through `ObjectStorage` if persistence is enabled; local UI run JSONs are demo artifacts only.
- Provider neutrality: no cloud SDK imports inside `agents/agent-05-editorial-planning/agent/`.

Agent 05 v1 does not need `TranscriptionProvider` because it has no voice/video input. If a future version accepts audio/video planning input, transcription must use `TranscriptionProvider` per ADR-0003.

## Access Control
- Invokers: marketers, content strategists, editors, founders, campaign managers, or the local demo UI.
- Runtime identity: its own least-privilege identity per deployment; local mock mode needs no cloud credentials.
- Reads: user-supplied brand/campaign inputs, optional existing ideas, optional constraints, and optional prior approved planning snippets supplied as direct context.
- Writes: structured planning package, local UI run JSONs in demo mode, logs/metrics through `Telemetry`, and optional provider-neutral storage references.
- External writes: none in v1.
- Secrets: provider credentials only through `SecretStore`.
- HITL-gated actions: all publishing, scheduling, calendar writes, CMS writes, analytics access, or social actions are out of scope in v1 and would require explicit human approval in a future version.
- Audit logging: provider calls, route decisions, status, quality score, risk flags, and cost metrics are emitted through `Telemetry` with sensitive content excluded.
- Data classification: brand strategy, campaign goals, and calendar plans are sensitive business content and must not be logged raw.

## Functional Requirements
- Accept brand/company name.
- Accept business goal.
- Accept target audience.
- Accept campaign theme.
- Accept one or more platforms.
- Accept date range.
- Accept posting frequency.
- Accept tone/brand voice.
- Accept content pillars/themes.
- Accept optional existing ideas.
- Accept optional constraints.
- Validate required inputs before billable work.
- Normalize platforms and posting cadence.
- Validate that date range and frequency are feasible.
- Create editorial calendar entries across the date range.
- Create weekly or monthly content plan summaries.
- Create platform-wise content plan summaries.
- Generate a content brief for each planned item.
- Recommend suggested title/topic for each item.
- Recommend content type for each item.
- Explain objective and audience fit.
- Suggest CTAs.
- Assign priority.
- Recommend planned publish date and internal due date.
- Map repurposing opportunities across platforms.
- Analyze balance across pillars, platforms, funnel stages, and content types.
- Flag risks and gaps.
- Produce a quality score.
- Return review notes and human-edit guidance.
- Fail safely on invalid or insufficient input.

## Non-Functional Requirements
- Latency target: planning request to package p50 around 20-35 seconds, p95 around 75 seconds in live mode.
- Cost target: under Rs15 per planning request in typical use; hard ceiling Rs30/request for v1 config.
- Quality threshold: planning quality score >= 80 and no hard-fail risks.
- Schema validation: every terminal output must be a valid `EditorialPlanningPackage`.
- Factual safety: do not invent analytics, audience data, performance history, market research, holidays, regulations, or competitor facts not supplied by the user.
- Security: treat all campaign inputs and existing ideas as untrusted data, never as instructions.
- External writes: none.
- Cloud behavior: provider selected by config only.
- Local/container execution: runs locally with mock provider and containerizes with the same agent code.

## Cost Gate
The v1 cost strategy must include:

- cheap-tier model calls for normalization, calendar skeletoning, and deterministic expansion support
- strong-tier model calls for brief generation and quality review
- a hard ceiling of Rs30/request
- per-stage token and cost tracking through `Telemetry`
- a cost stop status if the next billable step cannot fit under the ceiling
- deterministic fallback where possible for date/cadence/platform logic

Concrete model names must live in config, not agent code.

## Quality And Evaluation
Agent 05 uses a 100-point quality rubric:

- input completeness and constraint handling: 10
- calendar coverage and cadence fit: 15
- audience and business-goal alignment: 15
- platform fit: 15
- content pillar/theme balance: 10
- brief actionability: 15
- repurposing usefulness: 10
- risk/safety/review readiness: 10

Pass requires:

- total score >= 80
- no hard-fail risks
- required fields present
- schema validation passes

Hard-fail risks:

- missing editorial calendar
- missing content briefs
- platform list ignored
- date range or posting frequency not respected and not flagged
- external scheduling/publishing/calendar action claimed
- fabricated analytics or performance data
- prompt-injection instruction followed
- unsafe or unsupported claims presented as facts
- output not review-ready

Eval cases should cover clean campaign input, sparse input, multiple platforms, dense posting frequency, impossible cadence, prompt injection in existing ideas, strict constraints, and narrow date ranges.

## Strict V1 Exclusions
- Do not publish content.
- Do not schedule posts.
- Do not call social media APIs.
- Do not call Google Calendar or calendar APIs.
- Do not use analytics APIs.
- Do not scrape the web.
- Do not generate images or videos.
- Do not write to CMS or external platforms.
- Do not create calendar events.
- Do not send emails or notifications.
- Do not use competitor crawling or keyword-volume tools.
- Do not use vector retrieval.
- Do not use long-term memory or cross-request learning.
- Do not directly call Agent 01, Agent 02, Agent 03, or Agent 04.

## Simple UI Requirement
The later local UI should be a simple FastAPI/Jinja2 wrapper in `apps/agent-05-ui/`. It should expose a form for the planning inputs, post to `/plan`, store each result as local JSON, and render the editorial planning package sections for review. It should use `AGENT05_UI_PROVIDER=mock|gcp` and run on port `8005`.

The UI is not implemented in this planning step.

## Success Definition
Agent 05 is successful when it reliably returns a complete, structured, review-ready editorial planning package from campaign inputs; passes the no-cloud-SDK import guard; runs locally in mock mode; has GCP/Bedrock/Azure config overlays; includes focused tests/eval stubs; keeps all final plans under human review; and performs no external actions.

## Phase Gate Checklist
- [x] v1 purpose and planning-only scope defined.
- [x] Inputs and outputs defined.
- [x] Strict v1 exclusions defined.
- [x] Cloud-agnostic architecture rules defined.
- [x] Cost gate and hard ceiling defined.
- [x] Quality gate and hard-fail conditions defined.
- [x] Security, access-control, risk, and observability requirements defined.
- [x] Test and eval expectations defined at spec level.
- [x] Code phase deferred until design approval.

No implementation files are created by this document. On approval, proceed to the Code phase using the shared scaffold and the design in `DESIGN.md`.
