# Agent 02 Basic Content Repurposer UI

Minimal internal browser UI for the Content Repurposing Agent.

This is intentionally not a product frontend: no React, no Streamlit, no auth,
no database, and no publishing. It is a small FastAPI + Jinja2 wrapper around
the existing Agent 02 graph.

## Run Locally In Live GCP Mode

From PowerShell:

```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"
$env:VERTEX_AI_PROJECT="agents-platform-1212"
$env:PYTHONPATH="packages;agents\agent-02-content-repurposer"
Set-Location "apps\agent-02-ui"
python -m uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

The UI always uses the configured LiteLLM/Vertex provider and existing local
ADC credentials. These runs may incur billable model cost. If `GCS_BUCKET` is
set, Agent 02 can also make its best-effort ObjectStorage write; otherwise the
UI still saves the inline final schema JSON locally.

## Runtime Data

Run results are written to:

```text
apps/agent-02-ui/runs/{run_id}.json
```

Run JSON is ignored by git. The UI stores final package schemas only; it does
not print or persist secrets and has no publishing/social/CMS/CRM/ad actions.
