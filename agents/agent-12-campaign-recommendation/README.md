# Agent 12 - Campaign Recommendation Agent

Agent 12 creates ranked campaign recommendation packages for the Demand Generation pillar. It compares campaign options, recommends a primary path, outlines alternatives, budget guidance, KPIs, dependencies, experiment plans, and risks without launching or spending.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

``powershell
$env:PYTHONPATH = "packages;agents\agent-12-campaign-recommendation"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-12-campaign-recommendation\tests -q
``

Service usage:

``python
from agent.service import run

package = run({
    "business_context": "B2B workflow platform for revenue teams.",
    "product_or_service": "Revenue workflow automation",
    "campaign_goal": "Plan the next approved demand generation motion.",
})
``

## V1 Boundaries

No external writes or activation are allowed. Requests to spend budget, launch ads, send emails, upload audiences, update live campaigns, or run experiments return hard-fail risk flags and require human review plus future integration design.