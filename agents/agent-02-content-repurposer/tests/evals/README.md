# Agent 02 Offline Evals

This suite uses the shared `packages/evals` harness with deterministic mock
providers. It is a review-ready content-quality gate, not a live-provider gate.

Covered v1 cases:

- clean approved blog
- long technical article
- weak CTA that should be revised
- generic/boring source that should not pass
- multi-platform package with optional newsletter
- source prompt injection
- confidential/internal source
- thin input

Core thresholds:

- overall quality score >= 85 for pass cases
- factual consistency >= 90 for pass cases
- platform fit >= 85
- usefulness >= 85
- CTA clarity >= 85
- cost < Rs.30/package
- adversarial cases must route to terminal hard-fail statuses
