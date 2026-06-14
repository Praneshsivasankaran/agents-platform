# Agent 03 Content Ideation UI

Minimal internal browser UI for the Content Ideation Agent.

This is a small FastAPI + Jinja2 wrapper around the Agent 03 graph. It has no
authentication, database, publishing, analytics, scraping, or social API
integration.

## Run Locally

From the repository root:

```powershell
$env:AGENT03_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-03-content-ideation"
Set-Location "apps\agent-03-ui"
python -m uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Live GCP Mode

```powershell
$env:AGENT03_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "your-project"
$env:PYTHONPATH = "packages;agents\agent-03-content-ideation"
Set-Location "apps\agent-03-ui"
python -m uvicorn app:app --reload
```

Live mode makes billable model calls through `LLMProvider` and LiteLLM.

## Runtime Data

Run results are written to:

```text
apps/agent-03-ui/runs/{run_id}.json
```
