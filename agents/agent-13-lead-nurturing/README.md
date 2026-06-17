# Agent 13 - Lead Nurturing Agent

Agent 13 creates advisory lead nurturing journey packages for the Demand Generation pillar. It maps branches, touchpoints, cadence, triggers, exits, suppression, content gaps, sales handoff, and KPI plans without sending messages or writing automation workflows.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

``powershell
$env:PYTHONPATH = "packages;agents\agent-13-lead-nurturing"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-13-lead-nurturing\tests -q
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

No external writes or activation are allowed. Requests to send email or SMS, write MAP workflows, update CRM, activate retargeting, or launch journeys return hard-fail risk flags and require human review plus future integration design.