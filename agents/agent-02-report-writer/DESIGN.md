# Report Writing Agent — Design (Phase 2)

> Generated skeleton. Mirror agents/agent-01-blog-writer/DESIGN.md as this fills in.

## 1. Graph topology
Skeleton spine: `intake -> process -> finalize`. TODO — add the agent's real stages and the
quality/cost-gate control flow.

## 2. State
See `agent/state.py` (`ReportWriterState`). Accumulators use `operator.add`.

## 3. Provider abstractions
Model -> `LLMProvider`; storage -> `ObjectStorage`; secrets -> `SecretStore`; telemetry ->
`Telemetry`; transcription (if used) -> `TranscriptionProvider`. Selected by config via
`core.factory`. **No cloud SDK in `agent/`.**

## 7. Schemas
See `agent/schemas.py`. All typed I/O is `CoreContractModel` (frozen, deeply immutable).

## 8. Cost
One ledger (`core.cost`), USD->INR via `fx_rates`, Rs50 ceiling enforced pre-call (authorize_call)
and post-call (graph guard). Incurred cost is preserved on failures via `BillableNodeError`.

## 10. Security
Untrusted input is fenced by `agent/prompts.wrap_untrusted`, which neutralizes embedded fence
markers (no delimiter breakout). Raw media (if any) has short/no retention. Errors are sanitized
(type name only; no paths/secrets).

## Media
This is a TEXT-ONLY agent: no ffmpeg is installed. Re-generate with `--with-media` (or add the ffmpeg layer yourself) if the agent needs voice/video transcription.
