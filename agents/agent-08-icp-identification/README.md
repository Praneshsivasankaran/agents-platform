# Agent 08 - ICP Identification Agent

Agent 08 creates evidence-aware ICP planning packages for the Demand Generation pillar. It is a v1 advisory agent: it does not create account lists, enrich accounts, scrape, update CRM, upload audiences, or activate campaigns.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-08-icp-identification"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-08-icp-identification\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "business_context": "B2B workflow platform for revenue teams.",
    "product_or_service": "Revenue workflow automation",
    "source_notes": "Best customers are mid-market SaaS teams with complex handoffs.",
})
```

## V1 Boundaries

No external writes or activation are allowed. Requests to scrape, enrich, create account lists, update CRM, upload audiences, or target protected attributes return hard-fail risk flags and require human review plus future integration design.

