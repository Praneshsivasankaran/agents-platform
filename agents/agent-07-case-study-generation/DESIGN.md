# Agent 07 - Case Study Generation Agent Design

**Status:** Draft for design review  
**Date:** 2026-06-16  
**Program:** Stratova AI Agent Platform / ContentIQ  
**Pillar:** Content Marketing  
**Agent path:** `agents/agent-07-case-study-generation/`  
**Optional UI path:** `apps/agent-07-ui/`  
**Lifecycle phase:** 2 - Design  
**Next gate:** Human design approval before coding

---

## 1. Design goal

Agent 07 must convert raw customer success notes into a structured, credible, review-ready case study package while staying cloud-agnostic and safe. The design follows the existing agent platform pattern: typed Pydantic schemas, request-scoped state, deterministic validation/scoring tools, LangGraph-style orchestration, provider routing through shared core abstractions, and no cloud SDK imports inside `agent/`.

---

## 2. Orchestration / workflow steps

The agent should be implemented as a deterministic graph around LLM generation.

```text
1. intake_request
2. normalize_input
3. validate_minimum_story_context
4. extract_evidence_and_metrics
5. classify_story_angle
6. plan_case_study_structure
7. generate_title_options
8. draft_case_study_sections
9. generate_quotes_and_ctas
10. scan_claims_and_risks
11. score_quality
12. optional_revision_pass
13. assemble_case_study_package
14. finalize_response
```

### Step details

| Step | Purpose | Expected output |
|---|---|---|
| `intake_request` | Accept request and attach request id/config | Initial state |
| `normalize_input` | Trim text, normalize empty fields, standardize tone/platform options | Normalized request |
| `validate_minimum_story_context` | Check customer/background, challenge, solution, result | Missing info warnings or hard fail |
| `extract_evidence_and_metrics` | Extract metrics, baselines, before/after results, timeline | Evidence map and metric highlights |
| `classify_story_angle` | Choose story type: transformation, cost saving, productivity, growth, operational excellence, customer experience | Narrative angle |
| `plan_case_study_structure` | Create a section outline before drafting | Case study outline |
| `generate_title_options` | Generate 3-5 title options and choose one | Title list and recommendation |
| `draft_case_study_sections` | Generate the main case study sections | Draft sections |
| `generate_quotes_and_ctas` | Add pull quotes, placeholder customer quotes, and CTA options | Quote/CTA package |
| `scan_claims_and_risks` | Detect unsupported claims, invented metrics, quote risk, confidentiality issues | Risk flags |
| `score_quality` | Score draft using deterministic rubric | Quality report |
| `optional_revision_pass` | If score is below threshold but fixable, run one revision pass | Improved draft and updated score |
| `assemble_case_study_package` | Build stable output schema | Final package |
| `finalize_response` | Add cost usage, pass/fail, status | Response payload |

---

## 3. Tools

V1 should use only local/deterministic tools. No external systems are required.

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_case_study_input` | Normalized request | Missing fields, hard-fail reasons, completeness score | None | Local only |
| `extract_metric_candidates` | Source notes, results text | Metric candidates with source snippets and confidence | None | Local only |
| `normalize_metric_highlights` | Metric candidates | Clean metric highlight objects | None | Local only |
| `detect_unsupported_claims` | Draft, evidence map | Risk flags and unsupported-claim list | None | Local only |
| `score_case_study_quality` | Draft sections, warnings, risk flags | Quality score and dimension scores | None | Local only |
| `estimate_cost_usage` | Provider response metadata | Token/cost usage object | None | Local only |

No tool should read from CRM, CMS, analytics, web search, social media, internal databases, or customer data stores in v1.

---

## 4. Data sources and memory/state

### Data sources

- Request body fields.
- Optional pasted/uploaded source notes if existing UI pattern supports uploads.
- Optional previous agent output pasted into the request.

### Memory and retention

- Request-scoped state only.
- No long-term memory.
- No cross-request customer profile storage.
- Any persistence must happen only through approved platform abstractions and must be optional.

### Provider-swap behavior

State is plain typed Python/Pydantic data. It must not depend on any provider-specific SDK objects. GCP, Bedrock, and Azure provider changes should only affect provider config and shared LLM implementation, not Agent 07 logic.

---

## 5. Input schema proposal

Implement in `agent/schemas.py` using Pydantic.

```python
class CaseStudyRequest(BaseModel):
    customer_name: str | None = None
    anonymize_customer: bool = False
    industry: str | None = None
    target_audience: str
    challenge: str
    solution_summary: str
    product_or_service: str | None = None
    implementation_notes: str | None = None
    results: str
    metrics: list[MetricInput] = []
    customer_quotes: list[str] = []
    source_notes: str | None = None
    brand_voice: str | None = None
    tone: Literal["professional", "executive", "technical", "conversational"] = "professional"
    cta_goal: str | None = None
    output_length: Literal["short", "standard", "long"] = "standard"
    provider: str | None = None
    max_cost_rs: float | None = None
```

Supporting input objects:

```python
class MetricInput(BaseModel):
    label: str
    value: str
    baseline: str | None = None
    after: str | None = None
    source: str | None = None
```

---

## 6. Output schema proposal

```python
class CaseStudyPackage(BaseModel):
    request_id: str
    status: Literal["approve", "revise", "reject"]
    pass_status: Literal["pass", "fail"]
    recommended_title: str | None
    title_options: list[str]
    executive_summary: str | None
    customer_background: str | None
    challenge_section: str | None
    solution_section: str | None
    implementation_section: str | None
    results_section: str | None
    metric_highlights: list[MetricHighlight]
    pull_quotes: list[str]
    customer_quote_placeholders: list[str]
    cta_suggestions: list[str]
    final_markdown_draft: str | None
    missing_information_warnings: list[MissingInfoWarning]
    risk_flags: list[RiskFlag]
    quality_report: QualityReport
    cost_usage: CostUsage
```

Supporting output objects:

```python
class MetricHighlight(BaseModel):
    label: str
    value: str
    evidence: str | None
    confidence: Literal["high", "medium", "low"]

class MissingInfoWarning(BaseModel):
    field: str
    severity: Literal["low", "medium", "high"]
    message: str

class RiskFlag(BaseModel):
    category: Literal[
        "unsupported_claim",
        "invented_metric",
        "quote_risk",
        "confidentiality",
        "pii",
        "legal_review",
        "brand_risk"
    ]
    severity: Literal["low", "medium", "high", "hard_fail"]
    message: str
    evidence_needed: str | None = None

class QualityReport(BaseModel):
    overall_score: int
    dimension_scores: dict[str, int]
    approval_reason: str
    revision_notes: list[str]

class CostUsage(BaseModel):
    provider: str
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_rs: float
    cost_ceiling_rs: float
```

---

## 7. State model

Implement in `agent/state.py`.

```python
class Agent07State(TypedDict, total=False):
    request: CaseStudyRequest
    normalized_request: CaseStudyRequest
    request_id: str
    missing_information_warnings: list[MissingInfoWarning]
    hard_fail_reasons: list[str]
    evidence_map: dict[str, Any]
    metric_highlights: list[MetricHighlight]
    story_angle: str
    outline: dict[str, Any]
    title_options: list[str]
    recommended_title: str
    draft_sections: dict[str, str]
    pull_quotes: list[str]
    customer_quote_placeholders: list[str]
    cta_suggestions: list[str]
    risk_flags: list[RiskFlag]
    quality_report: QualityReport
    revision_attempted: bool
    cost_usage: CostUsage
    package: CaseStudyPackage
```

The state must remain serializable and should not contain provider SDK responses directly.

---

## 8. Prompt strategy

### System prompt principles

The agent prompt should instruct the model to:

- Act as a B2B case study strategist and content writer.
- Use only the provided evidence.
- Never invent customer quotes, customer approval, metrics, timelines, legal claims, or named references.
- Mark missing evidence clearly.
- Keep the output credible, specific, and review-ready.
- Prefer clear business language over hype.
- Preserve brand voice when provided.
- Return output in the required structured schema.

### Generation prompt stages

Use separate prompts where possible:

1. Story planning prompt: identify angle, evidence, and outline.
2. Drafting prompt: write sections using the outline and evidence map.
3. Risk review prompt or deterministic risk scan: detect unsupported or unsafe claims.
4. Revision prompt: improve only when the first draft is below threshold and not a hard fail.

### Output contract

The LLM output should be parsed into Pydantic models. If parsing fails, the service should retry once with a repair prompt or return a controlled error matching the existing agent error style.

---

## 9. Scoring strategy

`score_case_study_quality` should be deterministic and transparent.

| Dimension | Weight |
|---|---:|
| Challenge clarity | 15 |
| Solution specificity | 15 |
| Evidence-backed results | 20 |
| Credibility and claim safety | 15 |
| Structure completeness | 10 |
| Brand/tone fit | 10 |
| Readability | 10 |
| CTA usefulness | 5 |
| Total | 100 |

### Status thresholds

| Status | Rules |
|---|---|
| `approve` | overall score >= 85 and no high/hard-fail risk flags |
| `revise` | score 65-84, or minor/high warnings that are fixable |
| `reject` | score < 65, missing core story components, hard-fail risk, or unsupported major claims |

### Pass/fail

- `pass` if score >= 80 and no hard-fail flags.
- `fail` otherwise.

---

## 10. Risk handling

Risk handling is central for this agent because case studies can become public proof assets.

Hard-fail conditions:

- Challenge, solution, or results are missing.
- The draft contains a major unsupported result claim.
- A customer quote is presented as real when it was not supplied.
- Public customer name usage is implied without customer name or anonymization clarity.
- Sensitive/confidential input appears in a public-ready section without warning.

Medium/high warning conditions:

- Metrics lack baseline or source.
- Results are vague or qualitative only.
- Customer approval is not mentioned.
- Timeline is missing.
- CTA is not aligned with the target audience.

The final output should include warnings instead of silently hiding these issues.

---

## 11. Provider-neutral check

Agent 07 must follow these rules:

- `agent/` imports only local modules, standard library, Pydantic, LangGraph/framework utilities already used by the repo, and shared platform abstractions.
- No `google.cloud`, `vertexai`, `boto3`, `botocore`, `azure`, or cloud-specific SDK imports inside `agent/`.
- Provider selection happens through config overlays and the existing provider/core factory pattern.
- GCP can be wired as the live provider if current agents already do that.
- Bedrock and Azure must keep config/stub parity.
- Tests must include or reuse a banned-import scan.

---

## 12. Expected file layout

```text
agents/agent-07-case-study-generation/
  AGENT_SPEC.md
  DESIGN.md
  README.md
  Dockerfile
  config/
    base.yaml
    gcp.yaml
    bedrock.yaml
    azure.yaml
  agent/
    __init__.py
    schemas.py
    state.py
    prompts.py
    scoring.py
    workflow.py
    graph.py
    service.py
    errors.py
  tests/
    unit/
      test_schemas.py
      test_scoring.py
      test_workflow.py
      test_no_cloud_imports.py
    evals/
      cases/
        happy_path.json
        missing_metrics.json
        unsupported_claim.json
        quote_placeholder.json
        confidential_customer.json
      test_eval_agent07.py
```

Optional UI if consistent with previous agents:

```text
apps/agent-07-ui/
  app.py
  templates/
  static/
  README.md
```

---

## 13. Config design

`config/base.yaml` should define default thresholds and behavior:

```yaml
agent:
  id: agent-07
  name: case-study-generation
  version: 0.1.0

quality:
  pass_threshold: 80
  approve_threshold: 85
  revise_min_threshold: 65
  max_revision_attempts: 1

cost:
  max_cost_rs: 25.0

runtime:
  default_output_length: standard
  anonymize_customer_default: false
  require_source_for_metrics: true
```

Cloud overlays should follow previous agent patterns and should not introduce provider-specific logic into `agent/`.

---

## 14. Eval plan

### Eval cases

| Case | Purpose | Expected behavior |
|---|---|---|
| `happy_path` | Complete customer story with metrics | Approve/pass, full draft, high score |
| `missing_metrics` | Results are vague with no numbers | Revise/fail or revise/pass depending quality; no invented metrics |
| `unsupported_claim` | Input suggests exaggerated result without evidence | Risk flag and reject/fail if major claim appears |
| `quote_placeholder` | No real quote supplied | Placeholder only, no fake attribution |
| `confidential_customer` | Customer name marked confidential | Warning and anonymized-safe draft |
| `thin_input` | Missing challenge or solution | Reject/fail with missing info warnings |

### Metrics

- Schema validity rate.
- Required section coverage.
- Correct status label.
- Risk flag recall on adversarial cases.
- No invented metric rate.
- Average quality score behavior.
- Cost ceiling adherence.

### Thresholds

- 100% schema validity.
- 90%+ required-section coverage.
- 90%+ risk behavior accuracy.
- 0 invented metrics in eval cases.
- Cost <= configured ceiling for normal eval cases.

---

## 15. Unit testing plan

Unit tests should cover:

- Schema validation with required and optional fields.
- Missing information validator.
- Metric extraction and normalization edge cases.
- Quality scoring thresholds.
- Approve/revise/reject status mapping.
- Risk flag hard-fail behavior.
- Cost ceiling behavior.
- Banned cloud SDK import scan inside `agent/`.
- Workflow happy path using fake/stub LLM provider.
- Workflow fail path for missing challenge/solution/results.

---

## 16. Observability plan

Emit structured logs and trace spans for:

- Request received.
- Validation complete.
- LLM generation start/end.
- Risk scan complete.
- Quality scoring complete.
- Final status.

Log fields:

- `request_id`
- `agent_id`
- `provider`
- `model`
- `input_tokens`
- `output_tokens`
- `estimated_cost_rs`
- `quality_score`
- `status`
- `pass_status`
- `risk_flag_count`

Do not log full customer notes by default. If debug logging exists, it must be disabled by default and scrub sensitive data.

---

## 17. Error handling

Expected controlled errors:

| Error | When it happens | Response behavior |
|---|---|---|
| `InvalidCaseStudyInputError` | Required fields are empty or malformed | Return reject/fail with clear missing field messages |
| `CostCeilingExceededError` | Estimated cost exceeds configured ceiling | Return controlled failure before or after truncation strategy |
| `ModelOutputParseError` | LLM returns invalid structure after repair attempt | Return controlled failure with retry suggestion |
| `UnsafeClaimError` | Hard-fail unsupported claim detected | Return reject/fail with evidence-needed note |

Errors should match existing repo conventions if Agents 01-06 already define a shared pattern.

---

## 18. Manual test cases

Use these for local UI or service smoke testing:

### Manual test 1 - Complete B2B success story

Input includes named customer, clear challenge, solution, implementation notes, and metrics. Expected result: approve/pass, full case study, no hard-fail flags.

### Manual test 2 - No metrics

Input gives only qualitative result. Expected result: revise, missing metrics warning, no invented numbers.

### Manual test 3 - Fake quote risk

Input has no customer quote. Expected result: quote placeholders only, no attributed customer quote.

### Manual test 4 - Confidential customer

Input says customer name cannot be public. Expected result: anonymized draft and confidentiality warning.

### Manual test 5 - Thin story

Input misses challenge or solution. Expected result: reject/fail with clear missing information warnings.

---

## 19. Coding handoff after approval

After this design is approved, give Codex the implementation task with these instructions:

```text
Implement Agent 07 - Case Study Generation Agent using the approved AGENT_SPEC.md and DESIGN.md.
Follow the existing repo conventions from Agents 01-06.
Do not change shared architecture unless necessary.
Do not import cloud SDKs inside agent/.
Create tests and evals.
Run unit tests, evals, and banned-import scan.
Return files changed, commands run, failures, and whether it is safe to commit.
```

After Codex finishes, send the implementation to Claude for review:

```text
Review Agent 07 against AGENT_SPEC.md and DESIGN.md.
Check correctness, security, agnosticism, tests, evals, observability, provider config parity, and repo consistency.
Give PASS, PASS-with-fixes, or FAIL.
```

---

## 20. Design approval checklist

Before coding, confirm:

- [ ] Use case is correct.
- [ ] Scope boundaries are accepted.
- [ ] Inputs/outputs are enough for v1.
- [ ] ROI and efficiency assumptions are acceptable.
- [ ] Risk handling is strict enough for public case studies.
- [ ] Eval plan is concrete.
- [ ] Provider-neutral rules are clear.
- [ ] Optional UI decision is made.
