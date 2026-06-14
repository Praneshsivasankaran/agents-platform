# Agent 01 — Blog Writing Agent (golden / reference agent)

## Agent 03 Handoff

Agent 01 still accepts the original direct text/voice/video inputs. It also accepts an
optional `blog_brief_from_agent_03` structured field for Content Ideation handoff.
When present, that brief becomes the primary source for audience, campaign goal,
angle, outline, CTA, keywords, constraints, evidence placeholders, and risk flags.
The agent does not import Agent 03 code; it validates the serialized handoff with
a local Pydantic contract and keeps all provider calls behind existing interfaces.

Converts messy multi-modal input (text, voice, video-audio) into a **review-ready blog
package** (draft-only in v1). The reference pattern the other ~39 agents copy.

- **Spec:** [`AGENT_SPEC.md`](AGENT_SPEC.md) (Phase 1, approved)
- **Design:** [`DESIGN.md`](DESIGN.md) (Phase 2 — topology, state, schemas, gates, eval plan)
- **Framework:** LangGraph + LiteLLM + Pydantic (ADR-0001)

## Status
Code phase Increments 1-8 are complete and independently reviewed. Text, voice, and
audio-only video paths are implemented against provider-neutral interfaces; the shared
contracts, offline mocks/evals, GCP providers, Bedrock/Azure stubs, and `new-agent` scaffold
generator are in place.

All offline gates pass (**1417 tests**). The only remaining merge blocker is the credentialed
GCP live-smoke gate for Vertex AI, Cloud Speech-to-Text, and transient GCS storage; see
[`../../LIVE_SMOKE_REQUIRED.md`](../../LIVE_SMOKE_REQUIRED.md).

## Boundaries (fixed)
`agent/` is cloud-neutral (no cloud-SDK imports). v1 is draft-only: no publishing, CMS,
social, web search, scraping, visual-video analysis, or vector retrieval. Cost ceiling
₹50/blog; quality pass = score ≥ 80/100 AND no hard-fail.
