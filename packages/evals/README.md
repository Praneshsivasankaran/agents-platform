# Shared Eval Harness (`packages/evals`)

Agent-agnostic offline eval gate. Generalises the bake-off pattern
(`common/evals/asserts.py` + `cases.json`) into a reusable, hardened harness that all agents inherit.

**This is NOT a live-model quality proof.** It runs the agent graph against deterministic mock
LLM responses to verify routing, trust-boundary enforcement, cost accounting, and schema
contracts. Synthetic costs are used to test cost-gate wiring only.

## Architecture

- The **harness** (`harness.py`) lives here and is shared across all agents (not copied).
- Each agent's **datasets + thresholds** live per-agent in `agents/<agent>/tests/evals/`.
- Evals are **CI-gated** and datasets are **versioned** to prevent eval rot (DESIGN §9.4).

## All archetype/check policy is in YAML, NOT hardcoded in the harness

Policy that was previously hardcoded in `_ARCHETYPE_REQUIRED_CHECKS` is now configured in
`EvalThresholds` via three fields in the agent's `thresholds.yaml`:

```yaml
# Checks that must pass for EVERY case (regardless of archetype)
required_checks_all:
  - expected_status

# Checks that must pass for cases of a specific archetype
required_checks_by_archetype:
  prompt_injection:
    - injection_resisted
  pasted_reference:
    - originality_preserved

# Which archetypes contribute to injection_resistance_rate
injection_archetypes:
  - prompt_injection
```

This makes the harness genuinely agent-agnostic. New agents configure their own policy without
touching shared infrastructure.

## Immutable contracts

`EvalCase.graph_input`, `EvalCase.metadata`, `EvalObservation.check_results`, and
`EvalObservation.recorded_messages` use a checkpoint-safe immutable JSON representation:

- Backed by `FrozenJsonDict` (a `dict` subclass that blocks all mutation methods)
- Lists/tuples become `tuple` (immutable sequences)
- Pickle-safe: `pickle.dumps(case)` / `pickle.loads(...)` works correctly
- Deep-copy-safe: `model_copy(deep=True)` works correctly
- `model_dump(mode="json")` returns plain dicts and lists as expected
- Mutation (`case.graph_input["key"] = "x"`) raises `TypeError`
- Only JSON-compatible values accepted: `None`, `bool`, `int`, finite `float`, `str`,
  `str`-keyed dicts, lists/tuples of the above. Sets, bytes, Pydantic models, and
  non-string keys are rejected at construction time.

## Strict trust-boundary verification

`_check_injection_resisted` and `_check_originality_preserved` are **non-vacuous**:

- They **require** the protected content (canary / phrase) to appear in at least one
  recorded user message inside a correctly balanced `UNTRUSTED_DATA` block.
- Empty `recorded_messages` → `False` (cannot verify; fail-closed).
- Canary absent from all user messages → `False`.
- Canary anywhere in system messages → `False`.
- Canary outside `UNTRUSTED_DATA` block in any user message → `False`.
- Malformed blocks (unmatched markers, nested blocks) → `False`.

## Fail-closed FX configuration

The FX rate is read from `config/base.yaml` via `_extract_fx_rate(cfg)`. There is **no
hardcoded fallback**. Missing or invalid configuration fails immediately with a clear
`ValueError`:

- Missing `cost` section → `ValueError`
- Missing `fx_rates` → `ValueError`
- Missing `provider_currency` + no `USD` fallback → `ValueError`
- Zero or negative rate → `ValueError`
- Non-finite rate (NaN/inf) → `ValueError`

## How to run

```bash
# Run harness unit tests only
PYTHONPATH=packages python -m pytest packages/evals/tests -q

# Run Agent 01 eval gate
PYTHONPATH=packages:agents/agent-01-blog-writer python -m pytest agents/agent-01-blog-writer/tests/evals -q
```

## How to add a new agent's eval

1. Create `agents/YOUR-AGENT/tests/evals/` with `__init__.py`
2. Write `cases.vN.json` — versioned eval dataset (see `EvalDataset` schema)
3. Write `thresholds.yaml` — thresholds + archetype/check policy (see `EvalThresholds`)
4. Write `adapter.py` — bridges harness to the agent graph; implements `run_case()`
5. Write `test_eval.py` — loads dataset/thresholds, runs each case, asserts the report passes
6. Add `provider_currency` and `fx_rates` to the agent's `config/base.yaml`

See `agents/agent-01-blog-writer/tests/evals/` for the reference implementation.
