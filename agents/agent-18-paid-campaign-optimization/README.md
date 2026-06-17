# Agent 18 - Paid Campaign Optimization Agent

Agent 18 recommends paid campaign optimizations from supplied performance summaries. It is advisory only: it does not read ad platforms, change budgets, pause or launch campaigns, edit ads, upload audiences, or optimize live accounts.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-18-paid-campaign-optimization"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-18-paid-campaign-optimization\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "campaign_goal": "Improve paid search CPA",
    "platforms": ["Google Ads"],
    "metric_summary": "Spend Rs 120000, clicks 3200, conversions 80, CPA Rs 1500.",
})
```

## V1 Boundaries

All findings must be tied to supplied metrics, summaries, or clearly labeled assumptions. Budget recommendations are advisory and never authorization to change spend.
