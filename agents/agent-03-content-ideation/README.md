# Agent 03 - Content Ideation Agent

Agent 03 creates a structured Content Ideation Package from campaign context.
It is the strategy layer before Agent 01 writes a blog and Agent 02 repurposes
content.

## What It Does

- validates required campaign inputs
- summarizes the campaign
- analyzes the target audience
- generates content themes, ideas, hooks, and CTA suggestions
- scores and ranks ideas
- creates `blog_brief_for_agent_01`
- creates `repurposing_brief_for_agent_02`
- flags unsupported claims, live research requests, and weak ideas
- returns a typed `ContentIdeationPackage`

## What It Does Not Do

- no publishing or scheduling
- no social platform writes
- no CMS or CRM writes
- no web search, scraping, trend research, or SEO tools
- no direct imports from Agent 01 or Agent 02
- no cloud SDK imports inside `agent/`

## Run Locally

From the repository root:

```powershell
$env:PYTHONPATH = "packages;agents\agent-03-content-ideation"
python -m pytest agents\agent-03-content-ideation\tests
```

Programmatic use:

```python
from agent.service import run

package = run({
    "campaign_goal": "Build awareness for an AI planning product",
    "product_or_service": "ContentIQ",
    "target_audience": "B2B marketing managers",
    "industry": "B2B SaaS",
    "brand_tone": "clear, practical, confident",
    "key_message": "AI agents turn campaign context into structured content ideas.",
    "optional_keywords": ["content planning", "AI agents"],
    "number_of_ideas": 8,
})
```

## Config

- `config/base.yaml`: offline mock provider and Rs.20/package ceiling
- `config/gcp.yaml`: GCP/Vertex/LiteLLM overlay
- `config/bedrock.yaml`: AWS stub overlay
- `config/azure.yaml`: Azure stub overlay

Provider-specific code belongs in `packages/core`, not this agent.
