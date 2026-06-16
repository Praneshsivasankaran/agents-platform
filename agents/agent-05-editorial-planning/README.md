# Agent 05 - Editorial Planning Agent

Agent 05 turns brand, campaign, audience, platform, date range, cadence, tone, pillar, idea, and constraint inputs into a review-ready Editorial Planning Package.

## Inputs
- brand/company name
- business goal
- target audience
- campaign theme
- platforms
- date range
- posting frequency
- tone/brand voice
- content pillars or themes
- optional existing ideas
- optional constraints

## Outputs
- quality score and pass/fail status
- editorial calendar
- weekly/monthly plan
- platform-wise plan
- content briefs
- suggested titles/topics
- content type and objective
- CTA suggestions
- priorities and due dates
- repurposing map
- balance/gap analysis
- risk flags
- review notes

## V1 Exclusions
No publishing, scheduling, social posting, calendar APIs, analytics APIs, scraping, image/video generation, CMS writes, calendar events, email/notification sending, vector retrieval, long-term memory, cross-request learning, or direct calls to other agents.

## Run Agent Tests
From the repository root:

```powershell
$env:PYTHONPATH = "packages;agents\agent-05-editorial-planning"
python -m pytest agents\agent-05-editorial-planning\tests -q
```

## Run The Import Guard
```powershell
$env:PYTHONPATH = "packages"
python -m core.checks.no_cloud_sdk agents\agent-05-editorial-planning\agent
```

## Programmatic Use
```python
from agent.service import run

package = run({
    "brand_name": "Northstar Wellness",
    "business_goal": "Drive qualified leads for a corporate wellness program",
    "target_audience": "HR leaders at mid-market companies",
    "campaign_theme": "Burnout prevention for distributed teams",
    "platforms": ["blog", "linkedin", "email"],
    "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
    "posting_frequency": {"cadence": "weekly", "count_per_week": 3},
    "brand_voice": "warm, expert, practical",
    "content_pillars": ["education", "proof", "conversion"],
    "existing_ideas": ["Checklist for spotting team burnout"],
    "constraints": ["Avoid medical diagnosis claims"],
})
```

## Local UI (mock)
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform\apps\agent-05-ui"
$env:AGENT05_UI_PROVIDER = "mock"
$env:PYTHONPATH = "C:\Users\Pranesh\Desktop\agents-platform\packages;C:\Users\Pranesh\Desktop\agents-platform\agents\agent-05-editorial-planning"
& "C:\Users\Pranesh\Desktop\agents-platform\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005
```

Open `http://127.0.0.1:8005`.

## GCP / Vertex Live Mode
GCP is the only wired live provider. Bedrock and Azure remain structural config stubs.

```powershell
# one-time setup
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>

# run the UI live
Set-Location "C:\Users\Pranesh\Desktop\agents-platform\apps\agent-05-ui"
$env:AGENT05_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "<YOUR_PROJECT_ID>"
$env:PYTHONPATH = "C:\Users\Pranesh\Desktop\agents-platform\packages;C:\Users\Pranesh\Desktop\agents-platform\agents\agent-05-editorial-planning"
& "C:\Users\Pranesh\Desktop\agents-platform\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8005
```

Required env vars for GCP mode: `AGENT05_UI_PROVIDER=gcp`, `VERTEX_AI_PROJECT=<project-id>`, and
Google ADC (`gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`). If
`VERTEX_AI_PROJECT` is missing in GCP mode, the agent fails with a clear setup error and does not
silently fall back to mock. See `RUNBOOK.md` for the full checklist and the live GCP smoke test.

## Config
- `config/base.yaml`: offline mock provider, Rs30/request ceiling.
- `config/gcp.yaml`: GCP/Vertex overlay through shared `LLMProvider` and `VERTEX_AI_PROJECT`.
- `config/bedrock.yaml`: AWS stub overlay (not wired).
- `config/azure.yaml`: Azure stub overlay (not wired).

Provider-specific code belongs in `packages/core`, not this agent.

## Cost Control (live mode)
- Hard ceiling: Rs30/request; a typical GCP live run is ~Rs10.
- Every billable stage has a strict output-token cap and a pre-call worst-case budget check, so a
  stage is skipped before it starts if it could push the run over the ceiling.
- For large calendars, full LLM briefs are generated only for the top `max_full_briefs_live_mode`
  (default 5) highest-priority items; the rest get lighter deterministic summary briefs.
- If the budget runs low, the run degrades gracefully to `needs_review_budget_limited` with a
  partial-but-useful plan instead of a hard failure.

## Troubleshooting
- `needs_more_input`: fill all required campaign fields and use a valid date range.
- `needs_human`: review hard-fail risks and planning notes.
- `needs_review_budget_limited`: the run stayed under the cost ceiling by using deterministic
  fallbacks for some stages; review the partial plan, or re-run a smaller date range / fewer
  platforms for richer LLM output.
- `stopped_cost_ceiling`: shorten the date range, lower posting frequency, or reduce live-model output size.
- GCP live errors: set `VERTEX_AI_PROJECT`, authenticate with Google ADC, and use `AGENT05_UI_PROVIDER=gcp`.

## Known Limitations
- No live analytics, social, calendar, CMS, keyword, or competitor data.
- Date expansion is deterministic and approximate; a human should confirm workload.
- Planning packages are review-ready, not scheduled or published.

