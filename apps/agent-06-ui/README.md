# Agent 06 UI

Simple local FastAPI/Jinja2 wrapper for the Whitepaper Development Agent.

## Run

Mock/offline:

```powershell
$env:AGENT06_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-06-ui.app:app --host 127.0.0.1 --port 8006
```

Live GCP:

```powershell
gcloud auth application-default login
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:AGENT06_UI_PROVIDER = "gcp"
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-06-ui.app:app --host 127.0.0.1 --port 8006
```

The app stores run JSON files in `apps/agent-06-ui/runs/`.
