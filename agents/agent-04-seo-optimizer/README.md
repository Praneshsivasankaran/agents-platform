# Agent 04 - SEO Optimization Agent

Agent 04 turns a blog/article draft into a review-ready SEO Optimization Package. It improves metadata, headings, keyword placement, readability, FAQs, CTA direction, and draft structure while preserving the original meaning.

## Inputs
- draft content
- topic/title
- primary keyword
- optional secondary keywords
- target audience
- content goal
- brand tone
- constraints
- CTA direction

## Outputs
- SEO score and pass/fail status
- title options
- meta description
- URL slug
- recommended H1
- H2/H3 heading plan
- keyword placement suggestions
- readability fixes
- intro/conclusion improvements
- CTA suggestion
- FAQ suggestions
- risk flags
- editor notes
- optimized draft

## V1 Exclusions
No publishing, external content-system writes, social posting, Search Console, Analytics, scraping, competitor crawling, paid SEO APIs, backlink analysis, image SEO generation, database, auth, long-term memory, or cross-request learning.

## Run Agent Tests
From the repository root:

```powershell
$env:PYTHONPATH = "packages;agents\agent-04-seo-optimizer"
python -m pytest agents\agent-04-seo-optimizer\tests -q
```

## Run The Import Guard
```powershell
$env:PYTHONPATH = "packages"
python -m core.checks.no_cloud_sdk agents\agent-04-seo-optimizer\agent
```

## Programmatic Use
```python
from agent.service import run

package = run({
    "draft_content": "Full draft text...",
    "topic": "AI agents for content teams",
    "primary_keyword": "AI content agents",
    "secondary_keywords": ["content automation", "SEO workflow"],
    "target_audience": "marketing managers",
    "content_goal": "educate and generate demo interest",
    "brand_tone": "professional and clear",
    "constraints": ["Do not mention pricing"],
    "cta_direction": "Book a demo",
})
```

## Local UI
```powershell
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"
$env:AGENT04_UI_PROVIDER = "mock"
$env:PYTHONPATH = "$PWD\packages;$PWD\agents\agent-04-seo-optimizer"
Set-Location "apps\agent-04-ui"
python -m uvicorn app:app --host 127.0.0.1 --port 8004
```

Open `http://127.0.0.1:8004`.

## Config
- `config/base.yaml`: offline mock provider, Rs20/request ceiling.
- `config/gcp.yaml`: GCP/Vertex overlay through shared `LLMProvider` and `VERTEX_AI_PROJECT`.
- `config/bedrock.yaml`: AWS stub overlay.
- `config/azure.yaml`: Azure stub overlay.

Provider-specific code belongs in `packages/core`, not this agent.

## Troubleshooting
- `needs_more_input`: fill draft content, topic/title, and primary keyword.
- `needs_human`: review risk flags and editor notes.
- `stopped_cost_ceiling`: shorten the draft or reduce live-model output size.
- GCP live errors: set `VERTEX_AI_PROJECT`, authenticate with Google ADC, and use `AGENT04_UI_PROVIDER=gcp`.

## Known Limitations
- No live keyword volume, competitor, or analytics data.
- Readability is an approximate deterministic estimate.
- Optimized draft is review-ready, not publication-ready without human approval.
