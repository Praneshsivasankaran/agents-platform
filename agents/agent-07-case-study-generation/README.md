# Agent 07 - Case Study Generation Agent

Agent 07 creates a review-ready case study package from user-provided customer success context. It is draft-only: a human must verify customer approval, claims, metrics, quotes, and confidentiality before publication or sales use.

## Scope

Agent 07 accepts:

- customer or company name, or an anonymized label
- industry
- target audience
- challenge/problem
- product/service/solution used
- solution summary
- implementation or process notes
- results/outcomes
- metrics or ROI data
- customer quotes
- brand voice/tone
- CTA goal
- optional source notes

Agent 07 returns:

- title options and recommended title
- executive summary
- customer background
- challenge, solution, implementation, and results sections
- metric and ROI highlights
- pull quotes and quote placeholders
- CTA suggestions
- missing-information warnings
- unsupported-claim and confidentiality risk flags
- quality score, approval status, pass/fail status, and cost usage metadata

## V1 Boundaries

Agent 07 does not publish, write to a CMS, write to CRM/customer databases, call analytics, call social APIs, scrape the web, generate images/videos, or access customer data stores. It must not invent metrics, ROI, quotes, customer approval, legal approval, or named references.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM
- `bedrock.yaml` - structurally compatible stub overlay
- `azure.yaml` - structurally compatible stub overlay

Model names live in config only. Agent code never imports cloud SDKs or names provider models directly.

## Run Locally

Offline/mock tests:

```powershell
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-07-case-study-generation\tests -q
```

Local UI in mock mode:

```powershell
$env:AGENT07_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-07-ui.app:app --host 127.0.0.1 --port 8007
```

Live GCP UI:

```powershell
gcloud auth application-default login
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:AGENT07_UI_PROVIDER = "gcp"
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-07-ui.app:app --host 127.0.0.1 --port 8007
```

Open `http://127.0.0.1:8007`.

## Test Commands

```powershell
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-07-case-study-generation\tests\unit -q
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-07-case-study-generation\tests\evals -q
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-07-case-study-generation\tests\integration -q
.\.agent02-ui-venv\Scripts\python.exe -m pytest apps\agent-07-ui\tests -q
.\.agent02-ui-venv\Scripts\python.exe -m core.checks.no_cloud_sdk agents\agent-07-case-study-generation\agent
```

Live GCP smoke is opt-in and billed:

```powershell
$env:RUN_AGENT07_GCP_SMOKE = "1"
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-07-case-study-generation\tests\smoke -q
```
