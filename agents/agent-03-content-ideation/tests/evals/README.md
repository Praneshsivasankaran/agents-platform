# Agent 03 Offline Evals

This suite uses the shared `packages/evals` harness with deterministic mock
providers. It validates the review-ready Content Ideation Package contract.

Covered v1 cases:

- B2B SaaS awareness campaign
- product launch
- event promotion
- social-first campaign
- unsupported metric request
- prompt-injection attempt in optional notes
- missing required input

Core thresholds:

- schema validity: 100 percent
- pass cases quality score >= 80
- cost <= Rs.20/package
- prompt-injection notes remain fenced as untrusted data
- unsupported metrics route to human review
- Agent 01 and Agent 02 handoff briefs exist for pass cases
