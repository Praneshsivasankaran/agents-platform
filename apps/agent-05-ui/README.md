# Agent 05 UI

Thin FastAPI/Jinja2 wrapper for the Editorial Planning Agent. It is a thin client over the
shared agent graph + provider factory; it never imports a cloud or model SDK directly.

## Run — Mock mode (offline)
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform\apps\agent-05-ui"
$env:AGENT05_UI_PROVIDER = "mock"
$env:PYTHONPATH = "C:\Users\Pranesh\Desktop\agents-platform\packages;C:\Users\Pranesh\Desktop\agents-platform\agents\agent-05-editorial-planning"
& "C:\Users\Pranesh\Desktop\agents-platform\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005
```

Open `http://127.0.0.1:8005`.

## Run — GCP / Vertex live mode
Requires a billing-enabled GCP project with the Vertex AI API enabled, plus Google ADC.

```powershell
# one-time
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>

# run
Set-Location "C:\Users\Pranesh\Desktop\agents-platform\apps\agent-05-ui"
$env:AGENT05_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "<YOUR_PROJECT_ID>"
$env:PYTHONPATH = "C:\Users\Pranesh\Desktop\agents-platform\packages;C:\Users\Pranesh\Desktop\agents-platform\agents\agent-05-editorial-planning"
& "C:\Users\Pranesh\Desktop\agents-platform\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005
```

Form submissions in GCP mode make real, billed Vertex calls (capped per run by
`cost.ceiling_inr` in `config/gcp.yaml`).

## Provider Modes
- `AGENT05_UI_PROVIDER=mock` — offline deterministic mode (no credentials).
- `AGENT05_UI_PROVIDER=gcp` — GCP/Vertex live mode using `config/gcp.yaml` and `VERTEX_AI_PROJECT`.

GCP is the only wired live provider. Bedrock and Azure remain structural config stubs.

## Required env vars for GCP mode
| Variable | Required | Purpose |
| --- | --- | --- |
| `AGENT05_UI_PROVIDER=gcp` | yes | Selects the GCP overlay. |
| `VERTEX_AI_PROJECT` | yes | GCP project id (resolved via `EnvSecretStore`). |
| Google ADC | yes | `gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`. |

If `gcp` is selected and `VERTEX_AI_PROJECT` is missing, the UI fails with a clear setup error
that **names the missing variable** and does not silently fall back to mock.

The UI stores local JSON runs in `apps/agent-05-ui/runs/`. It does not publish, schedule, call
calendars, call social APIs, call analytics APIs, or write externally.
