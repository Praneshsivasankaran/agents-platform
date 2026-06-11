# Report Writing Agent (`agent-02-report-writer`)

Turns raw notes and source material into a structured, reviewed report.

Generated from the `new-agent` scaffold (Increment 8 / ADR-0004). The skeleton runs end-to-end
on the offline mock provider — no credentials required — and already enforces the platform's
Rs50 ceiling, honest cost accounting, and trust boundary.

## Run the tests (offline)

```bash
# POSIX/CI (use ';' instead of ':' on Windows)
PYTHONPATH=packages:agents/agent-02-report-writer python -m pytest agents/agent-02-report-writer/tests -q
PYTHONPATH=packages python -m core.checks.no_cloud_sdk agents/agent-02-report-writer/agent
```

## Layout

- `agent/` — cloud-neutral logic (state, schemas, graph, nodes, prompts). Imports only `core`.
- `providers/` — thin wiring to `core.factory` (no cloud-SDK imports).
- `config/` — `base.yaml` (mock, used by CI) + `gcp.yaml` / `bedrock.yaml` / `azure.yaml` overlays.
- `tests/` — `unit/`, `integration/`, `evals/`.

## Media

This is a TEXT-ONLY agent: no ffmpeg is installed. Re-generate with `--with-media` (or add the ffmpeg layer yourself) if the agent needs voice/video transcription.

## Specialize

1. Fill `AGENT_SPEC.md` and `DESIGN.md`.
2. Add stages to `agent/nodes/` and wire them in `agent/graph.py` (keep the budget gate in every
   billable node and preserve cost on failure via `BillableNodeError`).
3. Extend `ReportWriterState` and `ReportWriterPackage` with your typed artifacts.
4. Keep `agent/` free of cloud SDKs (CI enforces this).
