# Agent 04 SEO Optimizer UI

Minimal internal browser UI for Agent 04.

This is a small FastAPI + Jinja2 wrapper around the Agent 04 graph. It has no
authentication, database, publishing, analytics, scraping, or social platform
integration.

## Run Locally

From the repository root:

```powershell
$env:AGENT04_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-04-seo-optimizer"
Set-Location "apps\agent-04-ui"
python -m uvicorn app:app --host 127.0.0.1 --port 8004
```

Open:

```text
http://127.0.0.1:8004
```

## Live GCP Mode

```powershell
$env:AGENT04_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "your-project"
$env:PYTHONPATH = "packages;agents\agent-04-seo-optimizer"
Set-Location "apps\agent-04-ui"
python -m uvicorn app:app --host 127.0.0.1 --port 8004
```

Live mode makes billable model calls through `LLMProvider` and the shared core
provider implementation.

## Expected Venv Command

```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform\apps\agent-04-ui"
..\..\.agent04-ui-venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8004
```

If that venv does not exist, use the shared repo Python environment and set
`PYTHONPATH` as shown above.

## Runtime Data

Run results are written to:

```text
apps/agent-04-ui/runs/{run_id}.json
```
