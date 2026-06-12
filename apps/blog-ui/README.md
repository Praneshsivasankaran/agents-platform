# Agent 01 Basic Blog UI

Minimal internal browser UI for the Blog Writing Agent.

This is intentionally not a product frontend: no React, no auth, no database,
and no publishing. It is a small FastAPI + Jinja2 wrapper around the existing
Agent 01 graph.

## Run Locally In Live GCP Mode

From the repository root:

```powershell
python -m pip install -r requirements.txt
$env:VERTEX_AI_PROJECT = "agents-platform-1212"
$env:GCS_BLOG_BUCKET = "agents-platform-1212-agents-platform-stt-smoke"
$env:BLOG_UI_PROVIDER = "gcp"
$env:PYTHONPATH = "packages;agents\agent-01-blog-writer"
Set-Location "apps\blog-ui"
python -m uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

These runs make billable Vertex/Speech calls.

## Optional Offline Developer Mode

The public form does not show a provider selector. For tests or local debugging,
set the provider through the environment before starting the server:

```powershell
$env:BLOG_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-01-blog-writer"
Set-Location "apps\blog-ui"
python -m uvicorn app:app --reload
```

Mock mode needs no credentials and is intended for CI/developer checks only.

## Runtime Data

Run results are written to:

```text
apps/blog-ui/runs/{run_id}.json
```

Uploads are written under `apps/blog-ui/uploads/` only for the duration of the
request and are deleted after the graph returns. Raw media is not committed.
