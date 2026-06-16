# Agent 06 - Whitepaper Development Agent

## Use Case
Agent 06 creates a professional, review-ready whitepaper development package from user-provided business context. The user provides a topic, company or product context, target audience, industry, problem being solved, solution description, proof points or metrics, desired tone, target length/depth, CTA, and optional source notes. The agent returns a structured whitepaper development package or draft whitepaper package that a human can review, edit, and approve.

Agent 06 v1 is draft-only and context-only. It does not produce a final approved publication-ready whitepaper until a human has reviewed, verified, and approved the package. It does not publish, scrape, browse, perform live research, call external research APIs, write to a CMS, or claim that unsupported facts are verified. The agent must produce specific, business-ready content from the supplied context and must clearly mark missing evidence instead of inventing statistics, client names, case results, market numbers, or unverifiable claims.

## Why We Are Building This
Whitepapers are high-value B2B content assets, but they are slow to develop because they require clear positioning, audience-specific problem framing, solution depth, evidence discipline, and executive-ready structure. Teams often start from scattered notes, product messaging, sales context, proof points, and rough ideas. The manual process can lead to generic copy, unsupported claims, weak structure, missing evidence, and unclear handoffs to reviewers.

Agent 06 reduces the time required to turn raw business context into a structured whitepaper draft package while preserving human control over final accuracy, positioning, legal review, and publication. Its main value is not speed alone; its value is producing a specific, evidence-aware, review-ready foundation without generic AI filler.

## Position In Pipeline
Agent 06 sits in the long-form thought-leadership and sales-enablement layer:

- Agent 03 can provide campaign ideas or strategic content angles.
- Agent 05 can provide editorial plan context or a planned whitepaper brief.
- Agent 06 develops the whitepaper package from approved context.
- Agent 04 can later optimize related web/blog derivatives for SEO.
- Agent 02 can later repurpose an approved whitepaper into channel-specific content.

Agent 06 may accept optional structured context from prior agents, but it does not call other agents directly in v1. It returns structured output that a human or another tool may use later.

## ROI
- Manual whitepaper outlining and first-draft package: 8-16 hours.
- With Agent 06: 2-4 hours of human review, evidence filling, and editing.
- Time saved per whitepaper: about 6-12 hours.
- Volume assumption: 2 whitepaper projects/month.
- Monthly time saved: about 12-24 hours.
- Loaded B2B content/marketing cost: Rs1,000/hour.
- Monthly value: Rs12,000-Rs24,000.
- Annual value: Rs1,44,000-Rs2,88,000.
- Build cost: Rs30,000-Rs55,000.
- Annual run cost: Rs10,000-Rs25,000.
- Approx ROI: 150%-320%.
- Payback: roughly 2-5 months.

## Efficiency
- Baseline today: 8-16 hours of manual strategy, outlining, drafting, and evidence review per whitepaper package.
- Target with agent: 2-4 hours of human review and completion using a structured whitepaper package.
- Actual post-launch: fill after live use; track time saved, evidence-gap rate, reviewer edits, quality score, and cost/request.

## V1 Scope
Agent 06 v1 produces planning and draft-development artifacts only:

- whitepaper title options
- recommended angle
- executive summary
- target audience and reader pain points
- problem statement
- industry/context section
- proposed solution
- benefits
- use cases
- implementation approach
- risks/challenges
- conclusion
- CTA
- key claims and evidence status
- missing evidence or missing inputs
- quality score
- improvement suggestions

The output is review-ready draft material for human refinement. It is not a final approved publication asset.

## Inputs
Required inputs:

- topic
- company or product context
- target audience
- industry
- problem being solved
- solution description
- desired tone
- target length/depth
- CTA

Recommended inputs:

- proof points or metrics
- customer, user, or operational evidence
- differentiators
- target reader role and decision stage
- objections to address
- internal positioning notes
- approved messaging
- compliance or legal constraints

Optional inputs:

- source notes
- approved case-study snippets
- competitor positioning notes supplied by the user
- product feature notes
- implementation details
- sales enablement notes
- glossary or terminology preferences
- excluded topics or claims

All user-provided inputs are treated as untrusted data in prompts. They may influence the whitepaper package but cannot override system safety, provider-neutrality, evidence discipline, or v1 scope boundaries.

## Outputs
The terminal output is a `WhitepaperDevelopmentPackage` containing:

- normalized request summary
- whitepaper title options
- recommended angle
- executive summary
- target audience and reader pain points
- problem statement
- industry/context section
- proposed solution
- benefits
- use cases
- implementation approach
- risks and challenges
- conclusion
- CTA
- key claims and evidence status
- missing evidence or missing inputs
- quality score and pass/fail status
- improvement suggestions
- cost summary
- terminal status

Output must be schema-valid JSON when invoked through the agent service or UI API.

## Architecture Sketch
- Orchestration: LangGraph workflow with request-level state.
- Required internal workflow stages: intake validation -> context normalization -> angle planning -> evidence mapping -> outline generation -> section drafting -> claim/evidence review -> generic-content detection -> quality scoring -> final package assembly.
- Model routing: `LLMProvider` through shared core provider wiring. Agent logic never imports `litellm` or a direct model SDK.
- Typed I/O: Pydantic models based on shared core contract conventions.
- Cloud target: GCP/Vertex first through config; Bedrock and Azure remain structurally compatible stubs.
- Live path: GCP must be a working provider path through the existing provider/core abstraction. Mock providers are allowed for unit tests and offline CI, but the real local UI/service path must be able to run against the live GCP provider through config.
- Local tools: deterministic helpers for input completeness checks, section coverage checks, claim extraction, evidence-status classification, forbidden-claim detection, generic-language detection, CTA presence, and rubric scoring support.
- Memory/state: request-level state only; no long-term memory and no cross-request learning.
- Storage: generated whitepaper packages may be written through `ObjectStorage` if persistence is enabled; local UI run JSONs are demo artifacts only.
- Provider neutrality: no cloud SDK imports inside `agents/agent-06-whitepaper-development/agent/`.
- Provider selection: selected by config only; Bedrock and Azure overlays/stubs stay structurally compatible; model names must live in config and never in agent code.
- Later folder structure: follow Agent 05 with `agent/`, `providers/`, `config/`, `tests/unit/`, `tests/integration/`, `tests/evals/`, `README.md`, `RUNBOOK.md`, and Docker support when the code/design phases are approved.

Agent 06 v1 does not need `TranscriptionProvider` because it accepts text/context input only. If a future version accepts voice or video input, transcription must use `TranscriptionProvider` per ADR-0003.

## Access Control
- Invokers: marketers, founders, product marketers, content strategists, sales enablement teams, consultants, or the local demo UI.
- Runtime identity: its own least-privilege identity per deployment; local mock mode needs no cloud credentials.
- Reads: user-supplied topic, company/product context, audience, industry, problem, solution, tone, CTA, proof points, constraints, and optional source notes.
- Writes: structured whitepaper development package, local UI run JSONs in demo mode, logs/metrics through `Telemetry`, and optional provider-neutral storage references.
- External writes: none in v1.
- Secrets: provider credentials only through `SecretStore`.
- HITL-gated actions: all publication, CMS writes, CRM writes, email sending, file distribution, live research, analytics access, or external workflow actions are out of scope in v1 and would require explicit human approval in a future version.
- Audit logging: provider calls, route decisions, status, quality score, evidence flags, risk flags, and cost metrics are emitted through `Telemetry` with sensitive content excluded.
- Data classification: company strategy, product messaging, customer proof, source notes, and draft whitepaper content are sensitive business content and must not be logged raw.

## Functional Requirements
- Accept topic.
- Accept company or product context.
- Accept target audience.
- Accept industry.
- Accept problem being solved.
- Accept solution description.
- Accept proof points or metrics when provided.
- Accept desired tone.
- Accept target length/depth.
- Accept CTA.
- Accept optional source notes.
- Validate required inputs before billable work.
- Normalize the request into a structured summary.
- Identify the recommended whitepaper angle.
- Generate multiple title options.
- Draft an executive summary.
- Define target audience and reader pain points.
- Draft a problem statement.
- Draft an industry/context section using only provided context and clearly labeled general reasoning.
- Draft a proposed solution section.
- Draft benefits tied to the supplied product/company context.
- Draft use cases that stay within supplied context.
- Draft an implementation approach appropriate to the solution.
- Identify risks, challenges, objections, or adoption blockers.
- Draft conclusion and CTA.
- Extract key claims from the output.
- Assign evidence status to each key claim.
- List missing evidence and missing inputs.
- Score output quality.
- Return improvement suggestions.
- Fail safely on invalid, sparse, contradictory, or unsupported input.

## Non-Functional Requirements
- Latency target: context-to-package p50 around 25-45 seconds, p95 around 90 seconds in live mode.
- Cost target: under Rs30 per whitepaper package in typical use; hard ceiling Rs50/request for v1 config.
- Quality threshold: whitepaper quality score >= 80 and no hard-fail risks.
- Schema validation: every terminal output must be a valid `WhitepaperDevelopmentPackage`.
- Factual safety: do not invent statistics, client names, market numbers, case-study results, benchmarks, regulations, citations, dates, or quantified outcomes not supplied by the user.
- Evidence handling: unsupported or missing evidence must be clearly marked as missing, needs verification, or user-provided but unverified.
- Specificity: output must be specific to the provided company/product/topic and must avoid generic whitepaper filler.
- Security: treat all source notes and business context as untrusted data, never instructions.
- External writes: none.
- Cloud behavior: provider selected by config only.
- Local/container execution: runs locally with mock provider and containerizes with the same agent code.

## Cost Gate
The v1 cost strategy must include:

- cheap-tier model calls for request normalization, completeness checks, claim extraction, and outline/angle planning
- strong-tier model calls for main whitepaper section drafting and quality review
- a hard ceiling of Rs50/request
- per-stage token and cost tracking through `Telemetry`
- a cost stop status if the next billable step cannot fit under the ceiling
- deterministic fallback where possible for required-field checks, claim/evidence table checks, and generic-language checks

Concrete model names must live in config, not agent code.

## Quality Expectations
Content quality is the most important requirement for Agent 06. The output must be genuinely useful as content: specific, structured, professional, business-ready, and suitable for a marketing/content team to review and refine. It must not read like placeholder text or generic AI-style whitepaper filler.

The agent must reject, flag, or return improvement suggestions for weak/generic output. Average filler content must not pass the quality gate even if it has all required section headings.

Agent 06 uses a 100-point quality rubric:

- input completeness and constraint handling: 10
- specificity to company/product/topic: 15
- audience and pain-point fit: 10
- whitepaper structure and section completeness: 15
- problem-solution logic and business value: 15
- evidence discipline and claim labeling: 15
- depth, usefulness, and implementation actionability: 10
- tone, clarity, and executive polish: 5
- risk/challenge coverage and review readiness: 5

Pass requires:

- total score >= 80
- no hard-fail risks
- required fields present
- schema validation passes
- every key claim has an evidence status
- missing evidence is explicitly listed when applicable

Hard-fail risks:

- fabricated statistics, market numbers, benchmarks, client names, case-study results, citations, or quantified outcomes
- unsupported claims presented as verified facts
- missing key claims/evidence-status section
- missing missing-evidence/missing-inputs section
- generic whitepaper filler that is not specific to the provided company/product/topic
- target audience ignored
- problem or solution description ignored
- output claims live research, scraping, external validation, or external API usage occurred
- external publishing, CMS write, CRM write, email send, or file distribution claimed
- prompt-injection instruction followed
- unsafe, regulated, legal, medical, financial, or compliance-sensitive claims stated without user-provided evidence and review flags
- output not review-ready

Generic-content hard-fail guidance:

- generic whitepaper phrasing without company/product/topic specificity should fail or need human review
- repeated broad claims such as "drive innovation", "unlock value", or "transform your business" without concrete context should be flagged
- sections that merely restate headings without useful substance should not pass
- weak output should return improvement suggestions explaining what specific inputs, evidence, or rewrites are needed

## Evaluation Approach
Eval cases should cover:

- complete B2B SaaS whitepaper input with proof points
- sparse input with missing evidence
- product-led whitepaper for a technical buyer
- industry thought-leadership whitepaper with no supplied statistics
- heavily constrained tone/claims input
- prompt injection embedded in source notes
- contradictory proof points
- request for invented market numbers or client results
- long target-depth request under the cost ceiling
- narrow CTA and sales-enablement use case

Eval gates should check:

- schema validity for every terminal output
- quality score >= 80 on complete-input cases
- 100% fabrication resistance on unsupported statistics/client/result/market-number cases
- 100% prompt-injection resistance on injection cases
- every key claim has an evidence status
- missing evidence is flagged instead of invented
- output stays within draft-only scope
- no external action is claimed
- no cloud SDK imports inside `agent/`
- every eval run respects the Rs50/request hard cost ceiling

The evaluation suite should include deterministic checks for forbidden claims, evidence-status coverage, required section coverage, and generic-language risk, plus model-reviewed quality scoring where appropriate.

## Strict V1 Exclusions
- Do not publish whitepapers.
- Do not write to CMS or external platforms.
- Do not send emails or notifications.
- Do not upload or distribute files externally.
- Do not call CRM, marketing automation, analytics, calendar, or sales tools.
- Do not scrape the web.
- Do not perform live web research.
- Do not use external market-research APIs.
- Do not invent statistics, client names, case results, market numbers, citations, or source references.
- Do not claim source verification unless the user supplied the source and the output labels it correctly.
- Do not generate images, charts, or designed PDFs in v1.
- Do not use competitor crawling or keyword-volume tools.
- Do not use vector retrieval.
- Do not use long-term memory or cross-request learning.
- Do not directly call Agent 01, Agent 02, Agent 03, Agent 04, or Agent 05.

## Simple UI Requirement
The local UI should be a simple FastAPI/Jinja2 wrapper in `apps/agent-06-ui/`. It should expose a clean form for the required and optional whitepaper inputs, post to `/develop`, store each result as local JSON, and render the whitepaper development package sections for review. It should use `AGENT06_UI_PROVIDER=mock|gcp` and run on port `8006`.

Required UI fields: topic, company/product context, target audience, industry, problem, solution, tone, target depth, and CTA.

Optional UI fields: proof points, source notes, differentiators, objections, compliance/legal constraints, and excluded claims.

The UI must support live GCP provider execution through config. Mock mode may remain available for local offline checks and unit tests, but the actual live testing path must be able to call the GCP provider via the shared provider factory.

## Success Definition
Agent 06 is successful when it reliably returns a complete, specific, evidence-aware, review-ready whitepaper development package from user-provided context; passes the no-cloud-SDK import guard; runs locally in mock mode; has GCP/Bedrock/Azure config overlays; includes focused tests/eval stubs; keeps all final content under human review; clearly marks missing evidence; and performs no external actions.

## Phase Gate Checklist
- [x] v1 purpose and draft-only scope defined.
- [x] Inputs and outputs defined.
- [x] Strict v1 exclusions defined.
- [x] Cloud-agnostic architecture rules defined.
- [x] Cost gate and hard ceiling defined.
- [x] Quality gate, evidence rules, and hard-fail conditions defined.
- [x] Security, access-control, risk, and observability requirements defined.
- [x] Test and eval expectations defined at spec level.
- [x] Code and design phases deferred until planning approval.

No implementation files are created by this document. On approval, proceed to Phase 2 Design using the shared scaffold pattern and the Agent 05 structure.
