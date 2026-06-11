"""Agent 01 offline eval gate — all 7 archetypes.

Behavioral contract gate: schema validity, routing, trust boundaries, cost accounting.
NOT a live-model quality gate.
"""
from __future__ import annotations
import copy
import math
import pytest
from pathlib import Path

from evals import load_dataset, load_thresholds, evaluate, assert_eval_report, EvalObservation
from .adapter import run_case, _load_cfg, _extract_fx_rate

_DATASET_PATH = Path(__file__).parent / "cases.v1.json"
_THRESHOLDS_PATH = Path(__file__).parent / "thresholds.yaml"

# Module-scoped fixtures — run each case once for the entire module

@pytest.fixture(scope="module")
def _dataset():
    return load_dataset(_DATASET_PATH)

@pytest.fixture(scope="module")
def _thresholds():
    return load_thresholds(_THRESHOLDS_PATH)

@pytest.fixture(scope="module")
def _cfg():
    return _load_cfg()

@pytest.fixture(scope="module")
def _observations(_dataset, _thresholds, _cfg):
    obs = {}
    for case in _dataset.cases:
        observation = run_case(case, _cfg, _thresholds.offline_cost_per_call_inr)
        obs[case.id] = observation
    return obs

@pytest.fixture(scope="module")
def _report(_dataset, _observations, _thresholds):
    return evaluate(_dataset, list(_observations.values()), _thresholds)


_CASE_IDS = [
    "clean_text_001",
    "messy_notes_001",
    "pasted_reference_001",
    "voice_transcript_001",
    "video_transcript_001",
    "prompt_injection_001",
    "thin_input_001",
]


@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_schema_valid(case_id, _observations):
    obs = _observations[case_id]
    assert obs.schema_valid, f"case {case_id!r}: schema validation failed"


@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_expected_status(case_id, _observations):
    obs = _observations[case_id]
    assert obs.check_results.get("expected_status"), (
        f"case {case_id!r}: expected_status check failed "
        f"(terminal_status={obs.terminal_status!r})"
    )


@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_cost_under_ceiling(case_id, _observations, _thresholds):
    obs = _observations[case_id]
    assert obs.cost_inr < _thresholds.max_cost_per_run_inr_exclusive, (
        f"case {case_id!r}: cost={obs.cost_inr} >= ceiling={_thresholds.max_cost_per_run_inr_exclusive}"
    )


@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_required_checks_pass(case_id, _dataset, _observations):
    case = next(c for c in _dataset.cases if c.id == case_id)
    obs = _observations[case_id]
    for check_name in case.required_checks:
        assert obs.check_results.get(check_name), (
            f"case {case_id!r}: required check {check_name!r} failed"
        )


def test_aggregate_report_passes(_report):
    assert_eval_report(_report)


def test_injection_resistance_100_percent(_report):
    assert _report.injection_resistance_rate == 1.0, (
        f"injection_resistance_rate={_report.injection_resistance_rate} != 1.0"
    )


def test_schema_validity_100_percent(_report):
    assert _report.schema_validity_rate == 1.0, (
        f"schema_validity_rate={_report.schema_validity_rate} != 1.0"
    )


def test_pass_rate_at_least_80_percent(_report, _thresholds):
    assert _report.pass_rate >= _thresholds.minimum_pass_rate, (
        f"pass_rate={_report.pass_rate} < minimum={_thresholds.minimum_pass_rate}"
    )


def test_average_cost_within_target(_report, _thresholds):
    assert _report.average_cost_inr <= _thresholds.max_average_cost_inr_inclusive, (
        f"average_cost_inr={_report.average_cost_inr} > max={_thresholds.max_average_cost_inr_inclusive}"
    )


def test_determinism(_dataset, _thresholds, _cfg):
    """Two runs must produce identical observations."""
    obs1 = {c.id: run_case(c, _cfg, _thresholds.offline_cost_per_call_inr) for c in _dataset.cases}
    obs2 = {c.id: run_case(c, _cfg, _thresholds.offline_cost_per_call_inr) for c in _dataset.cases}
    for cid in obs1:
        assert obs1[cid].model_dump() == obs2[cid].model_dump(), (
            f"Non-deterministic observation for case_id={cid!r}"
        )


# Mutation tests

def _mutate_obs(observations: dict, case_id: str, **field_overrides) -> list[EvalObservation]:
    result = []
    for cid, obs in observations.items():
        if cid == case_id:
            data = obs.model_dump()
            for key, val in field_overrides.items():
                if key.startswith("check_results."):
                    check_name = key[len("check_results."):]
                    data["check_results"][check_name] = val
                else:
                    data[key] = val
            result.append(EvalObservation.model_validate(data))
        else:
            result.append(obs)
    return result


def test_mutation_injection_failure_detected(_dataset, _observations, _thresholds):
    mutated = _mutate_obs(_observations, "prompt_injection_001",
                          **{"check_results.injection_resisted": False})
    report = evaluate(_dataset, mutated, _thresholds)
    assert not report.passed
    assert any("injection_resisted" in f for f in report.failures)


def test_mutation_originality_failure_detected(_dataset, _observations, _thresholds):
    mutated = _mutate_obs(_observations, "pasted_reference_001",
                          **{"check_results.originality_preserved": False})
    report = evaluate(_dataset, mutated, _thresholds)
    assert not report.passed
    assert any("originality_preserved" in f for f in report.failures)


def test_mutation_thin_input_failure_detected(_dataset, _observations, _thresholds):
    mutated = _mutate_obs(_observations, "thin_input_001",
                          **{"check_results.thin_input_handled": False})
    report = evaluate(_dataset, mutated, _thresholds)
    assert not report.passed
    assert any("thin_input_handled" in f for f in report.failures)


def test_mutation_schema_validity_failure_detected(_dataset, _observations, _thresholds):
    first_id = list(_observations.keys())[0]
    mutated = _mutate_obs(_observations, first_id, schema_valid=False)
    report = evaluate(_dataset, mutated, _thresholds)
    assert not report.passed
    assert any("schema_validity" in f for f in report.failures)


def test_mutation_per_run_cost_over_ceiling_detected(_dataset, _observations, _thresholds):
    first_id = list(_observations.keys())[0]
    over_ceiling = _thresholds.max_cost_per_run_inr_exclusive  # == 50.0
    mutated = _mutate_obs(_observations, first_id, cost_inr=over_ceiling)
    report = evaluate(_dataset, mutated, _thresholds)
    assert not report.passed
    assert any("cost" in f.lower() for f in report.failures)


def test_mutation_average_cost_over_target_detected(_dataset, _observations, _thresholds):
    obs_list = []
    for obs in _observations.values():
        data = obs.model_dump()
        data["cost_inr"] = 30.0  # avg = 30 > 25
        obs_list.append(EvalObservation.model_validate(data))
    report = evaluate(_dataset, obs_list, _thresholds)
    assert not report.passed
    assert any("average" in f.lower() for f in report.failures)


def test_cost_uses_config_fx_rate(_dataset, _thresholds, _cfg):
    """Cost per call equals offline_cost_per_call_inr regardless of FX rate."""
    cfg_modified = copy.deepcopy(_cfg)
    cfg_modified["cost"]["fx_rates"]["USD"] = 100.0  # unusual FX rate

    # Run all cases with modified config
    obs_modified = {
        c.id: run_case(c, cfg_modified, _thresholds.offline_cost_per_call_inr)
        for c in _dataset.cases
    }
    # Original run
    obs_original = {
        c.id: run_case(c, _cfg, _thresholds.offline_cost_per_call_inr)
        for c in _dataset.cases
    }

    # Total cost should be the same (cost is determined by offline_cost_per_call_inr * call_count,
    # and the FX rate only affects how cost_native is computed from INR and converted back)
    # cost_native = cost_inr / fx_rate, then cost_inr = cost_native * fx_rate
    # So changing fx_rate doesn't affect cost_inr — the round-trip cancels out.
    for cid in obs_original:
        assert abs(obs_modified[cid].cost_inr - obs_original[cid].cost_inr) < 0.01, (
            f"case {cid!r}: cost_inr changed when FX rate changed — "
            f"offline cost should be FX-rate independent"
        )


# ---------------------------------------------------------------------------
# Issue 4 — Fail-closed FX rate extraction
# ---------------------------------------------------------------------------

def test_extract_fx_rate_succeeds_with_valid_config(_cfg):
    """_extract_fx_rate succeeds and returns (currency, rate) from base.yaml."""
    currency, rate = _extract_fx_rate(_cfg)  # unpack tuple
    assert isinstance(currency, str) and currency
    assert rate > 0 and math.isfinite(rate)


def test_extract_fx_rate_fails_on_missing_cost_section():
    """_extract_fx_rate raises ValueError when 'cost' section is absent."""
    with pytest.raises(ValueError, match="cost"):
        _extract_fx_rate({})


def test_extract_fx_rate_fails_on_missing_fx_rates():
    """_extract_fx_rate raises ValueError when 'fx_rates' is absent from config.cost."""
    with pytest.raises(ValueError, match="fx_rates"):
        _extract_fx_rate({"cost": {}})


def test_extract_fx_rate_fails_on_missing_provider_currency():
    """_extract_fx_rate raises ValueError when provider_currency is absent — no USD fallback."""
    cfg_no_currency = {"cost": {"fx_rates": {"USD": 83.0}}}  # missing provider_currency
    with pytest.raises(ValueError, match="provider_currency"):
        _extract_fx_rate(cfg_no_currency)


def test_extract_fx_rate_fails_on_zero_rate():
    """_extract_fx_rate raises ValueError when FX rate is zero."""
    with pytest.raises(ValueError, match="positive"):
        _extract_fx_rate({"cost": {"fx_rates": {"USD": 0.0}, "provider_currency": "USD"}})


def test_extract_fx_rate_fails_on_negative_rate():
    """_extract_fx_rate raises ValueError when FX rate is negative."""
    with pytest.raises(ValueError, match="positive"):
        _extract_fx_rate({"cost": {"fx_rates": {"USD": -1.0}, "provider_currency": "USD"}})


def test_extract_fx_rate_fails_on_nan():
    """_extract_fx_rate raises ValueError when FX rate is NaN."""
    with pytest.raises(ValueError, match="finite"):
        _extract_fx_rate({"cost": {"fx_rates": {"USD": math.nan}, "provider_currency": "USD"}})


def test_extract_fx_rate_fails_on_missing_currency_key():
    """_extract_fx_rate raises ValueError when configured currency is not in fx_rates."""
    with pytest.raises(ValueError, match="EUR"):
        _extract_fx_rate({"cost": {"fx_rates": {"USD": 83.0}, "provider_currency": "EUR"}})


def test_extract_fx_rate_deterministic_cost(_dataset, _thresholds, _cfg):
    """Cost is FX-rate independent: cost_native * rate always equals offline_cost_per_call_inr."""
    cfg_alt = copy.deepcopy(_cfg)
    cfg_alt["cost"]["fx_rates"]["USD"] = 100.0

    obs_orig = {c.id: run_case(c, _cfg, _thresholds.offline_cost_per_call_inr) for c in _dataset.cases}
    obs_alt = {c.id: run_case(c, cfg_alt, _thresholds.offline_cost_per_call_inr) for c in _dataset.cases}

    for cid in obs_orig:
        assert abs(obs_alt[cid].cost_inr - obs_orig[cid].cost_inr) < 0.01, (
            f"case {cid!r}: cost changed when FX rate changed"
        )
