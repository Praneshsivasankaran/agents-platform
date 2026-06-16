# Agent 07 - Case Study Generation Agent

**Status:** Draft for architecture approval  
**Date:** 2026-06-16  
**Program:** Stratova AI Agent Platform / ContentIQ  
**Pillar:** Content Marketing  
**Agent path:** `agents/agent-07-case-study-generation/`  
**Optional UI path:** `apps/agent-07-ui/`  
**Lifecycle phase:** 1 - Planning  
**Next gate:** Human architect approval before coding

---

## 1. Use case - what we are trying to do

Agent 07 turns raw customer success information into a review-ready business case study. A marketer, sales team member, or account manager provides rough notes such as customer background, business problem, product or service used, implementation details, measurable results, and preferred tone. The agent converts those notes into a structured case study package with title options, executive summary, challenge, solution, implementation, results, metric highlights, quote placeholders, CTA suggestions, risk flags, missing-information warnings, and a quality score.

The success definition is simple: a human reviewer should receive a credible, polished, structured case study draft that can be edited and approved faster than writing from scratch. The agent must not invent metrics, quotes, customer approvals, or unsupported claims. If source information is weak, the output must clearly warn the user instead of pretending the story is complete.

---

## 2. Where this agent will be used

This agent belongs to the Content Marketing block in the Marketing Transformation Pack. It fills the "Case Study Generation" capability and complements the existing Content Marketing agents:

| Existing / planned capability | Agent mapping | Status |
|---|---|---|
| Blog creation | Agent 01 | Completed |
| Content repurposing | Agent 02 | Completed |
| Content ideation | Agent 03 | Completed |
| SEO optimization | Agent 04 | Completed |
| Editorial planning | Agent 05 | Completed |
| Whitepaper development | Agent 06 | Completed |
| Case study generation | Agent 07 | This document |

Primary usage examples:

- Website customer success stories.
- Sales collateral and proof assets.
- Proposal-support case study inserts.
- Email campaign proof points.
- LinkedIn/customer story drafts that can later be passed to Agent 02 for repurposing.
- Internal knowledge base examples showing how Stratova/Laabu/RIVO helped a customer.

---

## 3. Business problem

Case studies are high-value marketing assets, but they are slow to create because the writer must collect the story, organize the narrative, extract measurable value, avoid unsupported claims, and make the final output usable by sales and marketing. Teams often have useful raw notes but no clean structure, or they have metrics without a strong story. Agent 07 reduces that friction by creating the first structured, review-ready version and highlighting exactly what is missing.

---

## 4. Users and triggers

**Primary users**

- Content marketers.
- Demand generation teams.
- Sales enablement teams.
- Account managers or customer success teams.
- Marketing coordinators preparing proof assets.

**Trigger**

The agent is triggered when a team has a customer/project success story and wants to turn it into a polished case study. Input may come from manual form fields, uploaded notes, an internal summary, or a future unified Content Marketing UI.

---

## 5. Inputs

Required inputs:

- Customer or company name, or an anonymized label.
- Industry or segment.
- Target audience.
- Business problem or challenge.
- Product, service, or solution used.
- Solution summary.
- Result or outcome notes.

Recommended inputs:

- Implementation or process notes.
- Measurable metrics and baseline/after values.
- Timeline.
- Customer quote or testimonial notes.
- Brand voice and tone guidance.
- CTA goal.
- Source notes or interview notes.
- Compliance or confidentiality notes.

Input should be accepted as typed form data and/or a structured JSON request. The design should not require any direct connection to CRM, CMS, analytics, or customer databases in v1.

---

## 6. Outputs

The agent returns a structured case study package containing:

- Title options.
- Recommended title.
- Executive summary.
- Customer background.
- Challenge/problem section.
- Solution section.
- Implementation/process section.
- Results/outcomes section.
- Metrics and ROI highlights.
- Pull quotes.
- Customer quote placeholders.
- CTA suggestions.
- Missing information warnings.
- Unsupported-claim risk flags.
- Confidentiality/PII warnings where relevant.
- Quality score.
- Approval status: `approve`, `revise`, or `reject`.
- Cost usage metadata.
- Final case study draft in review-ready format.

---

## 7. ROI

These are planning estimates and should be updated after the first real users test the agent.

**Assumptions**

- Case studies produced or refreshed: 8 per month.
- Current manual effort: 6 hours per case study.
- Target effort with agent: 1.5 hours per case study including review.
- Time saved: 4.5 hours per case study.
- Loaded content/sales enablement cost: Rs 1,000 per hour.
- Build cost using the existing agent template: Rs 120,000.
- Annual hosting, maintenance, and monitoring estimate: Rs 48,000.
- Inference estimate: Rs 20 per case study request, 96 requests/year = Rs 1,920/year.

**Annual value**

- Time savings: 8 case studies/month x 12 months x 4.5 hours saved x Rs 1,000 = Rs 432,000.
- Rework reduction value: estimated Rs 96,000/year.
- Throughput/reuse value from more proof assets: estimated Rs 120,000/year.
- Total estimated annual value: Rs 648,000.

**Cost**

- Build cost: Rs 120,000.
- Annual run cost: Rs 49,920.

**ROI estimate**

- ROI = (Annual value - Annual run cost) / (Build cost + Annual run cost)
- ROI = (Rs 648,000 - Rs 49,920) / (Rs 120,000 + Rs 49,920)
- ROI = Rs 598,080 / Rs 169,920 = 3.52, or about 352%.
- Estimated payback = Build cost / monthly net value = Rs 120,000 / (Rs 598,080 / 12) = about 2.4 months.

---

## 8. Efficiency

| Metric | Baseline today | Target with Agent 07 | Actual after launch |
|---|---:|---:|---|
| First draft creation time | 5-8 hours | 20-40 minutes | TBD |
| Human review/editing time | 2-4 hours | 45-90 minutes | TBD |
| Complete case study turnaround | 1-2 weeks | 1-2 days | TBD |
| Required structure coverage | Inconsistent | 95%+ required sections present | TBD |
| Unsupported claims caught | Manual / inconsistent | 90%+ flagged in evals | TBD |
| Draft quality score | No standard score | 80+ pass threshold | TBD |

---

## 9. Architecture sketch

**Orchestration shape**

A single-agent LangGraph-style workflow with typed state and deterministic validation/scoring steps around LLM generation.

**Model(s)**

- Primary LLM through the shared `LLMProvider` abstraction.
- Provider routing remains below the agent layer through the existing provider/core pattern.
- Cloud selected by config, not code.

**Tools**

V1 tools are local/deterministic helper tools only:

- Input completeness validator.
- Evidence and metric extractor.
- Claim risk checker.
- Case study structure assembler.
- Quality scorer.
- Cost ledger/usage normalizer.

No external system tools are required in v1.

**Data sources**

- User-submitted input fields.
- Optional user-provided notes or uploaded text.
- No CRM, CMS, analytics, web, social media, or customer database reads in v1.

**Memory/state**

- Request-scoped state only.
- No long-term memory in v1.
- Optional artifact persistence may use the platform `ObjectStorage` abstraction if previous agents follow that pattern, but the core agent must work without storage.

**Agnostic posture**

Agent 07 is cloud-agnostic. The agent logic must not import `google.cloud`, `vertexai`, `boto3`, `botocore`, `azure`, or any provider SDK inside `agent/`. GCP, Bedrock, and Azure must remain config/stub compatible through the platform abstraction layer.

---

## 10. Access control

| Area | Plan |
|---|---|
| Invokers | Marketing team, sales enablement, content lead, approved internal users |
| Runtime identity | Dedicated per-agent service identity, following the existing platform convention |
| Reads | User-submitted input and optional uploaded notes only |
| Writes | Response payload; optional generated artifact to object storage only if existing pattern supports it |
| Secrets | LLM/provider credentials through `SecretStore`; no secrets in code, config files, tests, or images |
| HITL-gated actions | Any publication, customer approval, CRM/CMS write, public quote usage, or external distribution |
| Audit | Log request id, model/provider, token/cost usage, quality score, risk flags, and final status |
| Data classification | Business confidential; may include customer names, commercial metrics, and testimonials |
| Data residency | Inherit platform deployment policy; do not add agent-specific cross-region movement |

---

## 11. Functional requirements

Agent 07 must:

1. Accept structured case study context as input.
2. Validate that the minimum story components are present: customer/background, challenge, solution, and result.
3. Identify missing information and ask for or warn about missing fields.
4. Extract and normalize metrics without inventing numbers.
5. Generate multiple title options and select a recommended title.
6. Produce a complete case study draft with standard sections.
7. Distinguish confirmed customer quotes from placeholder quote suggestions.
8. Flag unsupported claims, vague results, missing baselines, exaggerated statements, and risky public claims.
9. Generate CTA suggestions aligned to the campaign or sales goal.
10. Score the output using a deterministic rubric.
11. Return `approve`, `revise`, or `reject` based on thresholds and hard-fail rules.
12. Include token/cost usage metadata in the response.
13. Return output in a stable Pydantic schema suitable for UI rendering and eval checks.

---

## 12. Non-functional requirements

| Requirement | Target |
|---|---|
| Latency | p50 <= 35 seconds; p95 <= 90 seconds for normal inputs |
| Cost ceiling | Rs 25 per request hard ceiling unless config overrides it |
| Quality threshold | Pass if overall score >= 80 and no hard-fail risk flags |
| Availability | Same as platform service target; no special external dependency in v1 |
| Reliability | Deterministic validation and scoring should run even if LLM draft quality is weak |
| Security | No hardcoded secrets; no cloud SDK imports inside `agent/`; least-privilege runtime |
| Observability | Structured logs, trace spans, request id, provider, token count, cost, quality score |
| Compliance | Treat customer names, metrics, quotes, and internal notes as confidential input |
| Portability | Same agent package must run with GCP now and Bedrock/Azure stubs through config |
| Testability | Unit tests, schema tests, eval tests, and banned-import checks must be included |

---

## 13. Boundaries and out of scope

Agent 07 must not:

- Publish case studies.
- Write to a CMS.
- Write to CRM or customer databases.
- Call social media APIs.
- Call analytics APIs.
- Scrape the web.
- Generate images or videos.
- Claim customer approval unless explicitly provided.
- Invent metrics, customer quotes, legal approvals, or named references.
- Store long-term memory outside the platform-approved abstractions.
- Import cloud SDKs in `agent/`.

---

## 14. Quality gate and status logic

**Approve**

- Overall score >= 85.
- No hard-fail flags.
- Challenge, solution, and results are clear.
- Metrics are either sourced or clearly marked as missing.

**Revise**

- Overall score 65-84, or minor risk flags are present.
- Draft is usable but needs missing information, stronger metrics, or tone edits.

**Reject**

- Overall score < 65.
- Missing core story elements.
- Unsupported major claims.
- The case study would be misleading or unsafe to use without more information.

---

## 15. Eval requirements

The eval suite must include at least:

1. Happy path with complete customer story and metrics.
2. Missing metrics case where the agent must not invent numbers.
3. Vague input case where missing-information warnings are required.
4. Unsupported-claim case where risk flags are required.
5. Quote-placeholder case where quote suggestions must not be represented as real quotes.
6. Confidential customer case where public-usage warnings are required.

Minimum eval pass requirements:

- 100% schema-valid outputs.
- 90%+ required-section coverage across eval cases.
- 90%+ correct hard-fail/risk behavior on adversarial cases.
- Average quality score threshold behavior must match expected approve/revise/reject labels.

---

## 16. Implementation handoff boundary

This document approves only the planning scope. Do not code Agent 07 until `DESIGN.md` is reviewed and approved. After approval, Codex should implement against `AGENT_SPEC.md` and `DESIGN.md`, and Claude should review the resulting implementation for correctness, architecture fit, security, tests, evals, observability, and cloud-agnostic compliance.

---

## 17. Open questions for architect approval

1. Should Agent 07 include a local UI immediately, or only the agent package first?
2. Should generated case studies support multiple length modes in v1: short, standard, and long?
3. Should the agent generate HTML/Markdown output formats in v1, or only structured JSON plus plain Markdown draft?
4. Should customer names default to anonymized mode unless the user explicitly confirms public usage?
5. Should Agent 02 repurposing integration be added now, or left for the unified UI phase?
