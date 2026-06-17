# Agent 09 - Audience Segmentation Agent

Agent 09 creates evidence-aware audience segmentation packages for the Demand Generation pillar. It defines segments, inclusion/exclusion logic, suppression rules, overlap checks, channel fit, and handoffs without uploading or activating audiences.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

``powershell
$env:PYTHONPATH = "packages;agents\agent-09-audience-segmentation"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-09-audience-segmentation\tests -q
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

No external writes or activation are allowed. Requests to estimate audience size without supplied count data, upload audiences, target protected attributes, update CRM/MAP records, or launch campaigns return hard-fail risk flags and require human review plus future integration design.