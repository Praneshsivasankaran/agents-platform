# Agent 06 - Whitepaper Development Agent

Agent 06 creates a review-ready whitepaper development package from user-provided business context. It is draft-only: the package is not a final approved publication-ready whitepaper until a human verifies evidence, reviews claims, and approves the content.

## Scope

Agent 06 accepts:

- topic
- company/product context
- target audience
- industry
- problem
- solution
- tone
- target depth
- CTA
- optional proof points, source notes, differentiators, objections, compliance/legal constraints, and excluded claims

Agent 06 returns:

- title options
- recommended angle
- whitepaper sections
- key claims with evidence status
- missing evidence and missing inputs
- risk flags
- generic-content flags
- quality score and pass/fail status
- improvement suggestions

## V1 Boundaries

Agent 06 does not publish, scrape, browse, perform live research, call external research APIs, write to CMS/CRM/analytics/email systems, generate designed PDFs, use vector retrieval, or call other agents.

It must not invent statistics, citations, client names, market numbers, case results, benchmarks, or verified claims. Missing evidence is part of the output.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM
- `bedrock.yaml` - structurally compatible stub overlay
- `azure.yaml` - structurally compatible stub overlay

Model names live in config only. Agent code never imports cloud SDKs or names provider models directly.

## Run Locally

Offline/mock example:

```powershell
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-06-whitepaper-development\tests -q
```

Live GCP UI:

```powershell
gcloud auth application-default login
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:AGENT06_UI_PROVIDER = "gcp"
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-06-ui.app:app --host 127.0.0.1 --port 8006
```

Open `http://127.0.0.1:8006`.

## Test Commands

```powershell
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-06-whitepaper-development\tests -q
.\.agent02-ui-venv\Scripts\python.exe -m pytest apps\agent-06-ui\tests -q
```

Live GCP smoke is opt-in and billed:

```powershell
$env:RUN_AGENT06_GCP_SMOKE = "1"
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-06-whitepaper-development\tests\smoke -q
```
