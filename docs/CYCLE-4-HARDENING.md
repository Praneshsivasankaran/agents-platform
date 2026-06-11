# Cycle 4 — Debug / Harden (tracking checklist)

> Spiral Cycle 4 for the agents-platform. Entry state: Agent 01 Increments 1–8 complete;
> 1419 offline tests; 6/6 local live GCP smoke; live smoke wired through Workload Identity
> Federation; `main` protected with required checks `core-offline` and the live GCP smoke gate.
>
> **Scope discipline (unchanged from the code phase):** no publishing, scraping, vector
> retrieval, visual-video analysis, or CMS writes. The ₹50/run hard ceiling and the
> agnostic-by-construction rules (`agents/*/agent/` import only `core`; cloud SDKs only under
> `packages/core/providers/*`) remain FIXED, not tunable.

## Status legend
- ✅ done & verified offline
- 🟡 scaffold/proposal in place, deferred body or live verification pending
- ⏳ not started
- 🔒 gates merge / requires credentials or human action

## Checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Cycle 4 tracking checklist (this doc) | ✅ | — |
| 2 | Dependency reproducibility / lock strategy | ✅ | `constraints.txt` pins the live-smoke-verified direct deps; `docs/DEPENDENCY-MANAGEMENT.md` documents the floors-now / full-lock-later strategy. CI unchanged (opt-in `-c constraints.txt`). |
| 3 | infra/Terraform GCP scaffold | 🟡 | `infra/gcp/*.tf` — APIs, SA, WIF pool/provider, bucket+lifecycle, IAM. **No SA JSON keys** (WIF only). Not `terraform apply`-ed; `fmt`/`validate` to run where Terraform is installed. |
| 4 | GCP Secret Manager provider behind SecretStore | ✅ | `packages/core/providers/gcp/secret_manager.py`; factory `get_secret_store` selects it. Lazy SDK import; offline/mocked tests. No agent SDK imports. |
| 5 | Latency benchmark harness (offline) | ✅ | `packages/evals/benchmark.py` — p50/p95/p99 wall-clock over the mock graph; no live calls by default. |
| 6 | Expand adversarial evals | ✅ | Separate `cases.adversarial.v1.json` + `thresholds.adversarial.yaml` + `test_eval_adversarial.py` (keeps the v1 merge-gate dataset untouched). Injection variants, delimiter-breakout, verbatim-copy, unsafe-request, ambiguous, transcript-noise. |
| 7 | Retention / privacy tests | ✅ | Graph-level: raw input / draft / transcript never appear in telemetry. Transient GCS object deletion + temp-audio deletion already covered (cross-referenced). |
| 8 | Generate Agent 02 via new-agent CLI | ✅ | `agents/agent-02-report-writer/` scaffold (no business logic). Verified: compiles `-W error`, passes `no_cloud_sdk`, generated tests green. |
| 9 | Cloud-neutral invariant held | ✅ | `no_cloud_sdk` auto-discovery covers agent-02; provider SDKs confined to `packages/core/providers/*`. |
| 10 | No forbidden surfaces added | ✅ | No publishing/scraping/vector/visual-video/CMS introduced. |

## Verification gates (run each pass)
```
python -W error -m compileall -q packages agents
PYTHONPATH=packages python -m core.checks.no_cloud_sdk
PYTHONPATH=packages;agents/agent-01-blog-writer python -m pytest \
  packages/core/tests packages/evals/tests packages/cli/tests \
  agents/agent-01-blog-writer/tests --ignore=agents/agent-01-blog-writer/tests/smoke -q
```

## Still gating merge / requires human action (🔒)
- Independent Codex agnosticism + correctness review (ADR-0001 ratification gate).
- `terraform apply` of `infra/gcp/` against the real project (human + credentials).
- Production cutover of `secret_store.provider` from `env` → `gcp_secret_manager` in `gcp.yaml`
  once Secret Manager secrets are provisioned (currently env-backed; the provider is wired and
  tested but not the configured default).

## Observations found during Cycle 4 (candidate hardening, not bugs)
- **`untrusted_block` escapes embedded CLOSE markers but not OPEN markers.** The breakout vector
  is the *close* marker (escaping the fence), which IS escaped — so containment holds. But an
  embedded `--- BEGIN UNTRUSTED_DATA ---` in user input passes through unescaped, which the
  adapter's strict balanced-block parser treats as nesting. Not a containment hole (you cannot
  escape a block with an open marker), but escaping BOTH markers would make the wrapped output
  unambiguously single-block and the parser robust to adversarial open markers. Deferred:
  it touches load-bearing security code (and the generated `wrap_untrusted` mirror) and warrants
  its own reviewed change rather than riding in on an eval-expansion pass. The adversarial
  delimiter-breakout case tests the real (close-marker) vector.

## Deferred (tuning, not blocking)
- Caching of deterministic early stages; latency tuning to a real p50/p95 SLA using the harness.
- WER / transcription-quality measurement (ADR-0003, optional).
- Per-cloud tier→model calibration; AWS/Azure body-fill (interface-complete stubs exist).
- Agent-02+ business logic and a dedicated CI test job for each new agent.
