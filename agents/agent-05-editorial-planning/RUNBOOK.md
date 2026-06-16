# Agent 05 Runbook

Agent 05 (Editorial Planning) runs in two provider modes, selected by config only:

- **mock** — offline deterministic mode for local demo and CI. No credentials.
- **gcp** — live Vertex AI (Gemini) through the shared `LLMProvider`/LiteLLM abstraction.

Bedrock and Azure exist as **structural config stubs only** (`config/bedrock.yaml`,
`config/azure.yaml`). Selecting them constructs interface-complete stubs that raise
`NotImplementedError` when a model call is made. GCP is the only wired live provider.

## Local Mock Run (offline)
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"
$env:PYTHONPATH = "packages;agents\agent-05-editorial-planning"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-05-editorial-planning\tests -q
```

## UI — Mock mode
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform\apps\agent-05-ui"
$env:AGENT05_UI_PROVIDER = "mock"
$env:PYTHONPATH = "C:\Users\Pranesh\Desktop\agents-platform\packages;C:\Users\Pranesh\Desktop\agents-platform\agents\agent-05-editorial-planning"
& "C:\Users\Pranesh\Desktop\agents-platform\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005
```
Open `http://127.0.0.1:8005`.

## GCP / Vertex AI — Live mode

### 1. One-time GCP setup
Use a billing-enabled GCP project and enable Vertex AI:
```powershell
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>
```
The configured models must be available in the project (see `config/gcp.yaml`):
`vertex_ai/gemini-2.5-flash` (cheap) and `vertex_ai/gemini-2.5-pro` (strong).
The default Vertex location is `us-central1` (`llm.vertex_location` in `config/gcp.yaml`).

### 2. Required environment variables (live mode)
| Variable | Required | Purpose |
| --- | --- | --- |
| `AGENT05_UI_PROVIDER=gcp` | yes (UI) | Selects the GCP overlay in the UI. |
| `VERTEX_AI_PROJECT` | yes | Your GCP project id. Resolved via `EnvSecretStore` (`llm.vertex_project_secret`). |
| Google ADC | yes | `gcloud auth application-default login` **or** `GOOGLE_APPLICATION_CREDENTIALS=<service-account.json>`. |
| `GCS_BUCKET` | no | Only needed if object/output storage is later enabled. The v1 planning workflow and UI do not use storage. |

If `AGENT05_UI_PROVIDER=gcp` and `VERTEX_AI_PROJECT` is missing, the UI **fails with a clear
setup error and lists the missing variable** — it never silently falls back to mock.

### 3. Run the UI in GCP mode
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform\apps\agent-05-ui"
$env:AGENT05_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "<YOUR_PROJECT_ID>"
$env:PYTHONPATH = "C:\Users\Pranesh\Desktop\agents-platform\packages;C:\Users\Pranesh\Desktop\agents-platform\agents\agent-05-editorial-planning"
& "C:\Users\Pranesh\Desktop\agents-platform\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005
```
Open `http://127.0.0.1:8005`. Submit the form to make real (billed) Vertex calls. Cost is
capped per run by `cost.ceiling_inr` (Rs30) in `config/gcp.yaml`.

### 4. Live GCP smoke test (credentialed, billed)
Opt-in and skipped by default. Set the gate and project, then run only the smoke directory:
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"
$env:RUN_AGENT05_GCP_SMOKE = "1"
$env:VERTEX_AI_PROJECT = "<YOUR_PROJECT_ID>"
$env:PYTHONPATH = "packages;agents\agent-05-editorial-planning"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-05-editorial-planning\tests\smoke -q
```
The smoke test exercises: provider/config forwarding, a live cheap-tier text call, a live
structured call, and a full end-to-end editorial-planning run — all with positive, finite,
capped cost. If `RUN_AGENT05_GCP_SMOKE=1` is set but `VERTEX_AI_PROJECT` is missing, the suite
**errors loudly** rather than skipping.

## No-cloud-SDK import guard
Agent logic must never import a cloud or model SDK. Verify:
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"
$env:PYTHONPATH = "packages"
.\.agent02-ui-venv\Scripts\python.exe -m core.checks.no_cloud_sdk agents\agent-05-editorial-planning\agent
```

## Safety Checklist
- No publishing.
- No scheduling.
- No social API calls.
- No Google Calendar or calendar API calls.
- No analytics APIs.
- No scraping.
- No image or video generation.
- No CMS writes.
- No emails or notifications.
- No vector retrieval or long-term memory.
- No direct calls to other agents.
