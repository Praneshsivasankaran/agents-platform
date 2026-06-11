# AGENTS.md — Codex Instructions for Agent Platform

## Project Context

We are building a cloud-agnostic AI Agent Platform with around 40 reusable agents.

Current agent: Agent 01 — Blog Writing Agent.

Agent 01 is the golden/reference agent. Its implementation must become the reusable pattern for future agents.

Claude Code is the main builder. Codex is the parallel reviewer. Codex should review architecture, scope, tests, security, and cloud-agnostic correctness before the next coding increment continues.

## Source of Truth

Before reviewing or changing anything, read:

* `agents/agent-01-blog-writer/AGENT_SPEC.md`
* `agents/agent-01-blog-writer/DESIGN.md`
* `docs/adr/ADR-0001-framework-selection.md`
* `docs/adr/ADR-0003-transcription-provider.md`

These documents define the approved scope, architecture, framework, quality gates, cost limits, security posture, and implementation direction.

## Finalized Decisions

* Framework: LangGraph + LiteLLM + Pydantic
* v1 input: text, voice, video
* video v1: audio extraction + transcription only
* v1 output: review-ready blog package
* v1 is draft-only
* no publishing
* no social media posting
* no CMS writes
* no autonomous web search
* no web scraping
* no visual video/key-frame analysis
* no vector retrieval in v1
* past samples are direct-context only
* hard cost ceiling: ₹50/blog
* quality pass: score >= 80/100 and no hard-fail conditions
* GCP/Vertex AI is first target
* AWS Bedrock and Azure AI/Azure OpenAI must remain stubbed behind the same interfaces

## Cloud-Agnostic Rules

Agent logic must be cloud-neutral.

Inside `agents/agent-01-blog-writer/agent/`, there must be no direct imports or calls to:

* GCP SDKs
* Vertex SDKs
* AWS SDKs
* boto3 / botocore
* Azure SDKs
* direct STT cloud SDKs

All model calls must go through:

* `LLMProvider` + LiteLLM

All transcription must go through:

* `TranscriptionProvider`

All storage must go through:

* `ObjectStorage`

All secrets must go through:

* `SecretStore`

All traces, logs, metrics, token usage, and cost tracking must go through:

* `Telemetry`

Cloud/provider selection must happen through config, not hardcoded agent logic.

Provider-specific code belongs outside `agent/`.

## Review Role

Codex should act as a strict reviewer.

Do not expand scope.

Do not add publishing, scraping, visual video analysis, vector retrieval, or external write actions.

Do not approve code that violates the provider-neutral architecture.

Do not approve code that bypasses the abstractions.

Do not approve code that only works for one cloud by hardcoding GCP/Vertex inside agent logic.

## What to Check in Every Review

Check for:

1. Alignment with `AGENT_SPEC.md`
2. Alignment with `DESIGN.md`
3. Correct LangGraph workflow structure
4. Correct LiteLLM usage through `LLMProvider`
5. Correct Pydantic schema usage
6. Correct `TranscriptionProvider` usage
7. No cloud SDK imports inside `agent/`
8. No scope creep beyond v1
9. Cost gate and ₹50/blog ceiling
10. Quality gate, hard-fail rules, and revision loop
11. Draft-only security posture
12. Proper tests/evals
13. No secrets in code/config/logs
14. Clean repo structure
15. Whether this pattern can be reused for future agents

## Review Output Format

For reviews, respond with:

* Overall verdict
* Critical issues
* Recommended improvements
* Things that look good
* Final status: approve / approve with changes / reject

Prefer clear, actionable comments.
