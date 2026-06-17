# Agent 15 - Keyword Research Agent

Agent 15 creates evidence-aware keyword strategy packages for the Digital Marketing pillar. It is advisory only: it does not scrape SERPs, query Search Console, call SEO tools, check rankings, buy keywords, publish content, or change ad accounts.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-15-keyword-research"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-15-keyword-research\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "product_or_service": "Revenue workflow automation",
    "campaign_goal": "Build paid search plan",
    "target_audience": "RevOps leaders",
    "keywords": ["lead routing automation", "revops workflow"],
})
```

## V1 Boundaries

No live keyword, ranking, SEO, browser, CMS, ad platform, analytics, CRM, or MAP integrations are allowed in v1. Search volume, CPC, ranking, difficulty, and conversion data must be user-supplied or marked missing.
