# Agent 14 - Conversion Analysis Agent

Agent 14 creates deterministic-first conversion analysis packages for the Demand Generation pillar. It calculates conversion rates and drop-offs from supplied funnel counts, ranks bottlenecks, suggests hypotheses, optimization recommendations, and experiment backlog items without modifying live systems.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

``powershell
$env:PYTHONPATH = "packages;agents\agent-14-conversion-analysis"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-14-conversion-analysis\tests -q
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

No external writes or activation are allowed. Requests to change budgets, pause campaigns, launch experiments, modify live systems, or query analytics platforms return hard-fail risk flags and require human review plus future integration design.