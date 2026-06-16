# Agent 07 Runbook

## Purpose

Agent 07 produces a draft case study package for human review. It is not a final public-approved customer story.

## Required Inputs

- industry
- target audience
- challenge/problem
- solution summary
- results/outcomes

Recommended inputs:

- customer/company name or anonymization preference
- product/service used
- implementation notes
- metrics or ROI data
- customer quotes
- source notes
- brand voice/tone
- CTA goal

## Local UI

Mock/offline:

```powershell
$env:AGENT07_UI_PROVIDER = "mock"
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-07-ui.app:app --host 127.0.0.1 --port 8007
```

Live GCP:

```powershell
gcloud auth application-default login
$env:VERTEX_AI_PROJECT = "<your-gcp-project>"
$env:AGENT07_UI_PROVIDER = "gcp"
$env:PYTHONPATH = "packages;agents\agent-07-case-study-generation"
.\.agent02-ui-venv\Scripts\python.exe -m uvicorn apps.agent-07-ui.app:app --host 127.0.0.1 --port 8007
```

## Quality Review Checklist

- Challenge, solution, implementation, and results are specific.
- Metrics are sourced or clearly marked as missing.
- No invented ROI, approval, testimonial, legal claim, or external verification appears.
- Quote outputs are placeholders unless the user supplied approved quote text.
- Confidentiality and anonymization warnings are visible.
- Quality score is at least 80 for pass.
- Approval status is `approve` only when no material missing information or risk flags remain.
- Human review is completed before public use.

## Failure Statuses

- `approve` - review-ready package with strong evidence handling.
- `revise` - usable draft but missing useful context or risk review is needed.
- `reject` - required context, claim safety, or cost/error handling prevents safe use.

## Prohibited V1 Actions

Agent 07 must not publish, scrape, browse, call analytics, write to CMS/CRM/customer databases, post to social media, generate media assets, access customer data stores, or call other agents directly.
