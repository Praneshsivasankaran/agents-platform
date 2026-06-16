# Agent 06 Runbook

## Purpose

Agent 06 produces a whitepaper development package or draft whitepaper package for human review. It is not a final publication-approved whitepaper.

## Required Inputs

- topic
- company/product context
- target audience
- industry
- problem
- solution
- tone
- target depth
- CTA

Optional inputs:

- proof points
- source notes
- differentiators
- objections
- compliance/legal constraints
- excluded claims

## Local UI

Mock/offline:

```powershell
$env:AGENT06_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-06-ui.app:app --host 127.0.0.1 --port 8006
```

Live GCP:

```powershell
gcloud auth application-default login
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:AGENT06_UI_PROVIDER = "gcp"
$env:PYTHONPATH = "packages;agents\agent-06-whitepaper-development"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-06-ui.app:app --host 127.0.0.1 --port 8006
```

## Quality Review Checklist

- The output is specific to the company/product/topic.
- Every key claim has an evidence status.
- Missing evidence is clearly listed.
- No invented statistics, citations, client names, case results, market numbers, or benchmarks appear.
- Generic content flags are empty for a pass.
- Quality score is at least 80.
- Status is `pass` only when hard-fail risks are absent.
- Human review is completed before publication.

## Failure Statuses

- `needs_more_input` - required fields are missing or invalid.
- `needs_human` - quality or hard-fail risks require review.
- `needs_review_budget_limited` - one or more billable stages were skipped to preserve cost ceiling.
- `stopped_cost_ceiling` - cost ceiling prevented safe completion.
- `error` - unexpected workflow failure.

## Prohibited V1 Actions

Agent 06 must not publish, scrape, browse, perform live research, call external research APIs, write to CMS/CRM/analytics/email systems, or call other agents.
