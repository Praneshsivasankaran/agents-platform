# Agent 01 Offline Eval Gate

## What it is

This is a **behavioral contract gate** — NOT a live-model quality proof.

It runs Agent 01's full graph pipeline against deterministic mock LLM responses to verify
that routing, trust-boundary enforcement, cost accounting, and schema contracts all hold
correctly. Synthetic costs (`offline_cost_per_call_inr = ₹2/call`) are used to test the
cost-gate wiring, not to measure actual API costs.

## How to run

```bash
PYTHONPATH=packages:agents/agent-01-blog-writer python -m pytest agents/agent-01-blog-writer/tests/evals -q
```

## 7 archetypes covered

| Archetype | Case ID | Description |
|---|---|---|
| `clean_text` | `clean_text_001` | Well-formed prose input — happy path |
| `messy_notes` | `messy_notes_001` | Bullet-point / shorthand notes requiring normalization |
| `pasted_reference` | `pasted_reference_001` | User pastes copyrighted reference material — originality gate |
| `voice_transcript` | `voice_transcript_001` | Disfluent voice transcript (text representation) |
| `video_transcript` | `video_transcript_001` | Multi-speaker video transcript |
| `prompt_injection` | `prompt_injection_001` | Adversarial injection attempt — trust-boundary gate |
| `thin_input` | `thin_input_001` | Input too sparse to draft — thin-input escalation path |

## What passes / fails

Thresholds (see `thresholds.yaml`):

- `schema_validity_rate >= 1.0` — all observations must produce valid `BlogPackage` schemas
- `pass_rate >= 0.80` — computed over `pass_rate_archetypes` (clean_text, messy_notes, voice_transcript, video_transcript)
- `injection_resistance_rate == 1.0` — all prompt_injection cases must resist the attack
- `cost_inr < ₹50` per run (exclusive ceiling)
- `average_cost_inr <= ₹25` per run

Harness-mandated checks (configured in `thresholds.yaml`, NOT hardcoded in harness):
- Every case (`required_checks_all`): `expected_status` must pass
- `prompt_injection` cases (`required_checks_by_archetype`): `injection_resisted` must pass
- `pasted_reference` cases: `originality_preserved` must pass
- `thin_input` cases: `thin_input_handled` must pass

## FX rate

The FX rate is read from `config/base.yaml` (`cost.provider_currency` + `cost.fx_rates`).
There is no hardcoded fallback — missing or invalid configuration fails immediately.

## Limitations

- **Voice/video archetypes use the text pipeline** — Increment 6 adds dedicated media routing.
  These cases pass text-format transcripts through the standard normalize/extract/plan/draft pipeline.
- **Synthetic costs only** — offline runs use ₹2/call to test cost-gate wiring. Actual API
  costs depend on provider, model tier, and prompt length; run against a live provider overlay
  for real cost data.
- **Mock LLM responses** — behavioral coverage is determined by the mock scenario, not the
  model's actual generative quality. For live-model quality proof, run against a real provider.
