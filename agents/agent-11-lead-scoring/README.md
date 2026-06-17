# Agent 11 - Lead Scoring Agent

Agent 11 creates rule-based, explainable lead scoring packages for the Demand Generation pillar. It summarizes supplied signals into weights, thresholds, score bands, explanations, routing handoffs, and data quality warnings without updating CRM or MAP scoring fields.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

``powershell
$env:PYTHONPATH = "packages;agents\agent-11-lead-scoring"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-11-lead-scoring\tests -q
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

No external writes or activation are allowed. Requests to use protected attributes, leaky outcome fields, train black-box models, update CRM/MAP scores, or route leads automatically return hard-fail risk flags and require human review plus future integration design.