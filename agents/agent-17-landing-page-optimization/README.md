# Agent 17 - Landing Page Optimization Agent

Agent 17 creates landing page optimization briefs from supplied page and campaign context. It is advisory only: it does not crawl websites, read heatmaps, query analytics, publish pages, update CMS content, or launch tests.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-17-landing-page-optimization"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-17-landing-page-optimization\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "campaign_goal": "Increase demo requests",
    "target_audience": "RevOps leaders",
    "offer": "Workflow automation assessment",
    "page_copy": "Hero: Fix lead handoff delays. CTA: Book an assessment.",
})
```

## V1 Boundaries

URL-only requests are not crawled. Users must supply page copy, outlines, wireframe notes, or screenshot text notes as direct context.
