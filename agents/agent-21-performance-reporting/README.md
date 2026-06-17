# Agent 21 - Performance Reporting Agent

Agent 21 creates truthful stakeholder-ready performance reports from supplied metrics. It is advisory only: it does not query analytics, publish dashboards, read warehouses, query CRM/MAP/ad platforms, or send reports.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-21-performance-reporting"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-21-performance-reporting\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "campaign_goal": "Report paid search launch performance",
    "reporting_period": "May 2026",
    "metric_summary": "Impressions 10000, clicks 500, conversions 40, spend Rs 60000.",
})
```

## V1 Boundaries

Reports must not hide negative results, fabricate improvement, or overstate attribution. Rate and delta calculations use supplied metrics only.
