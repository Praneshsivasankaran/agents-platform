# packages/cli

Home of the `new-agent` scaffold generator that stamps out the per-agent skeleton for
agents 02–40 (so they are generated, never hand-rolled).

**Extracted LAST** — recorded in [ADR-0004](../../docs/adr/ADR-0004-scaffold-cli-sequencing.md): Agent 01 is hand-built as the reference, then the
CLI is crystallized from its now-stable structure and validated by regenerating Agent 01's
own skeleton and diffing. This aligns with the Spiral method (Cycle 5 generalizes after
Agent 01 is proven) and resolves the DESIGN §18 vs §14 tension — the true code-start
precondition is "`packages/core` exists," not "the CLI exists."

## Usage (Increment 8 — implemented)

```bash
# from the repo root
PYTHONPATH=packages python -m cli.new_agent \
  --number 02 --slug report-writer --title "Report Writing Agent" \
  --description "Turns raw notes into a structured report."

# voice/video agent (adds the ffmpeg layer + a transcription config stanza):
PYTHONPATH=packages python -m cli.new_agent --number 03 --slug call-summarizer \
  --title "Call Summarizer" --with-media
```

This creates `agents/agent-02-report-writer/` with a **runnable, cloud-neutral** skeleton:
`agent/` (state, schemas, graph, nodes intake→process→finalize, prompts with a trust-boundary
wrapper), `providers/`, `config/{base,gcp,bedrock,azure}.yaml`, `tests/{unit,integration,evals}/`,
plus `AGENT_SPEC.md`, `DESIGN.md`, `Dockerfile`, and `README.md`. The generated spine runs
end-to-end on the offline mock provider with no credentials, ships green tests, and passes the
no-cloud-SDK guard. A new agent specializes from there (add stages, schemas, prompts) without
touching the platform seams. Class names derive from the slug
(`report-writer` → `ReportWriterState` / `ReportWriterPackage`).

### Platform guarantees baked into every generated agent

The scaffold inherits Agent 01's load-bearing guarantees so they propagate to all 40 agents:

- **FIXED ₹50 ceiling** — the generated `process` node gates the call with
  `estimate_prompt_tokens` + `max_prompt_tokens` + `authorize_call`; a pre-call rejection becomes
  `status="stopped_cost_ceiling"` and the provider is never called. The graph guard adds a
  post-call ceiling check.
- **Honest cost on failure** — a `BillableProviderError` is converted to a generated
  `BillableNodeError` carrying the usage-derived `StageCost`; post-response and telemetry
  span-exit failures use the same path; the graph guard appends the cost and `safe_finalize`
  preserves the ledger (never reports ₹0 over real spend).
- **Trust boundary** — `wrap_untrusted` neutralizes embedded fence markers, so untrusted input
  cannot terminate the fence and escape into instructions.
- **Cloud-neutral** — `agent/` imports only `core`; cloud is chosen by config (`base.yaml` mock;
  `gcp`/`bedrock`/`azure` overlays).

Inputs are validated (`title`/`description` reject control chars, newlines, quotes, backslashes,
and the `@@` token marker). There is **no `--force`**: generation refuses an existing target
(protecting Agent 01 and preventing stale files) and only accepts agent numbers `02`–`40`.
Media (voice/video) is opt-in via `--with-media`; text-only agents ship neither ffmpeg nor a
transcription configuration stanza.

### What the generator guarantees (see `tests/test_new_agent.py`)

- Generated agent **compiles** (`-W error`), passes **`no_cloud_sdk`**, and its **own hardened
  tests pass** offline (ceiling block, billed-cost preservation, trust-boundary breakout) — run
  subprocess-isolated so the generated top-level `agent` package never collides with Agent 01's,
  with the parent dependency path preserved.
- The generated agent's **contract surface** matches the reference (Package status `Literal`,
  `StageCost.tier`, `build_graph`, `BillableNodeError`).
- A **bidirectional** regenerate-and-diff gate (`skeleton_parity_violations`) uses an independent
  canonical reusable manifest and checks generator-only and reference-only drift. Agent 01-specific
  files must be explicitly classified; an unclassified new reference file fails the gate. The only
  generated-only difference vs. the hand-built reference is the generic `agent/nodes/process.py`
  stage. Drift-regression tests prove the gate fails in both directions.
