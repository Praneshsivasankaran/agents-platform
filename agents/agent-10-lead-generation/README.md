# Agent 10 - Lead Generation Agent

Agent 10 creates advisory lead generation campaign blueprints for the Demand Generation pillar. It plans campaign motion, offer, capture path, landing page and form briefs, qualification rules, KPIs, and handoffs without creating individual lead records.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

``powershell
$env:PYTHONPATH = "packages;agents\agent-10-lead-generation"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-10-lead-generation\tests -q
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

No external writes or activation are allowed. Requests to scrape contacts, buy lead lists, enrich contacts, generate contact lists, send messages, update CRM/MAP records, or launch campaigns return hard-fail risk flags and require human review plus future integration design.