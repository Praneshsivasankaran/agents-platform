# Agent 19 - Multi-Channel Campaign Planning Agent

Agent 19 turns a chosen campaign direction into a coordinated multi-channel execution plan. It is advisory only: it does not launch ads, schedule posts, send emails or SMS, write MAP/CRM workflows, publish pages, upload audiences, or spend budget.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-19-multi-channel-campaign-planning"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-19-multi-channel-campaign-planning\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "campaign_goal": "Launch a RevOps benchmark campaign",
    "target_audience": "RevOps leaders",
    "offer": "Benchmark assessment",
    "timeline": "Six-week launch window",
    "channels": ["paid search", "email", "LinkedIn", "landing page"],
})
```

## V1 Boundaries

Calendar items are planning artifacts, not scheduled posts or sends. Consent, suppression, and human approval are required before any external activation.
