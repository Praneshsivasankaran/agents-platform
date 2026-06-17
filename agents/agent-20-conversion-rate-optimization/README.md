# Agent 20 - Conversion Rate Optimization Agent

Agent 20 creates CRO diagnoses, hypothesis backlogs, and experiment plans from supplied context. It is advisory only: it does not read analytics, change websites, launch experiments, write A/B testing configurations, personalize automatically, or update CMS content.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-20-conversion-rate-optimization"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-20-conversion-rate-optimization\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "conversion_goal": "Increase demo request form submissions",
    "target_audience": "RevOps leaders",
    "page_notes": "Users drop off near the pricing proof section.",
    "metric_summary": "Visitors 1000, form starts 120, submissions 45.",
})
```

## V1 Boundaries

Causal lift claims require supplied experiment evidence. Experiment priorities are planning heuristics and require human approval before implementation.
