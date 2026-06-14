# Agent 02 - Content Repurposing Agent

Agent 02 turns approved long-form content into a review-ready package of
platform-specific drafts for LinkedIn, Instagram, X/Twitter, short-video script,
and optional newsletter/email.

It is cloud-neutral and follows Agent 01's reference pattern: LangGraph workflow,
`LLMProvider`, typed `CoreContractModel` schemas, central `core.cost` accounting,
telemetry, evals, and no cloud SDKs inside `agent/`.

## V1 Scope

V1 is draft-only. It returns review-ready content and validation reports. It does
not publish, schedule, post, send email, write to a CMS/CRM/ad platform, scrape,
search the web, or perform irreversible external actions.

## Input

Pass a serialized source and campaign request as `raw_input`.

```python
{
    "source_type": "agent01_blog_package",
    "source_status": "pass",
    "title": "Repurposing without losing trust",
    "summary": "A workflow for turning approved content into channel-native drafts.",
    "blog_body": "...approved long-form body...",
    "target_platforms": ["linkedin", "instagram", "x_twitter", "short_video"],
    "audience": "B2B marketing teams",
    "brand_tone": "clear and practical",
    "campaign_goal": "turn one article into review-ready social drafts",
    "cta": "Read the full guide before planning next week."
}
```

Default platforms are LinkedIn, Instagram, X/Twitter, and short-video script.
Set `include_newsletter: true` to add newsletter/email.

Agent 02 also accepts optional `repurposing_brief_from_agent_03` strategy
guidance from the Content Ideation Agent. This field can provide target
audience, recommended platforms, platform-specific direction, hooks, CTA
direction, content pillars, tone rules, message guardrails, risk flags, and
quality notes. The brief guides strategy only; the source article/blog remains
the factual base for all repurposed outputs.

## How drafts are produced

`generate_platform_drafts` (and the revision step) ask the `LLMProvider` for a
structured `LLMDraftBundle` (one draft per platform). That LLM output is parsed
into validated `PlatformDraft`s and given deterministic structural finishing
(length-fit, hashtag clamping, thread/scene assembly). The deterministic
platform/usefulness/factual/quality validators then run over the **LLM-authored**
content as guardrails — so generic or ungrounded model output still fails the
gate. If the structured response is missing or too thin for a platform, that
platform falls back to a deterministic template; an entirely missing/invalid
response falls back to templates for all platforms. Offline runs on the mock
provider take the deterministic fallback and stay reproducible.

## Output

The graph returns `RepurposedContentPackage` with:

- platform drafts
- markdown review package
- validation/factual/usefulness/quality reports
- CTA options and hashtag sets
- hard-fail list
- cost ledger
- terminal status

Best-effort object storage can write a JSON package when configured, but inline
output is always returned.

## Run

```powershell
python -m pytest agents/agent-02-content-repurposer/tests -q
python -m pytest agents/agent-02-content-repurposer/tests/evals -q
python -m core.checks.no_cloud_sdk agents/agent-02-content-repurposer/agent
```

The exact handoff gate also includes:

```powershell
python -m ruff check agents/agent-02-content-repurposer packages
python -m mypy agents/agent-02-content-repurposer packages
```

## Cost And Quality

- Hard ceiling: Rs.30/package
- Pass score: >= 85/100
- Pass cases must have no hard-fails
- Generic rewriting, weak CTAs, unsupported claims, fake statistics, changed
  meaning, and repeated platform copy do not pass

## Layout

- `agent/workflow.py`: canonical LangGraph workflow
- `agent/graph.py`: compatibility re-export
- `agent/nodes/`: node factories
- `agent/schemas.py`: typed contracts (incl. `LLMDraftBundle` LLM-output schema)
- `agent/validators.py`: deterministic rules, scoring, and LLM-draft coercion/fallback
- `agent/prompts/`: prompt trust boundaries
- `config/`: mock and cloud overlay configs
- `tests/`: unit, integration, eval gates
