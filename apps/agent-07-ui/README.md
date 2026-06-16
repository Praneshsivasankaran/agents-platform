# Agent 07 UI

Simple local FastAPI/Jinja2 wrapper for the Case Study Generation Agent.

## Run

Mock/offline:

```powershell
$env:AGENT07_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-07-ui.app:app --host 127.0.0.1 --port 8007
```

Live GCP:

```powershell
gcloud auth application-default login
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:AGENT07_UI_PROVIDER = "gcp"
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-07-ui.app:app --host 127.0.0.1 --port 8007
```

The app stores run JSON files in `apps/agent-07-ui/runs/`.
