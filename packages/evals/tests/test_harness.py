"""Unit tests for the shared eval harness (packages/evals/harness.py).

Covers: model validation, evaluate() logic (all failure modes), assert_eval_report,
file loaders, edge cases (empty sets, NaN/inf, boundary costs), Issue 1 config-based
archetype/check policy, Issue 2 checkpoint-safe immutability.
"""
from __future__ import annotations

import json
import math
import pickle
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals import (
    EvalCase, EvalDataset, EvalThresholds, EvalObservation, EvalReport,
    load_dataset, load_thresholds, evaluate, assert_eval_report,
)


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------

def _make_case(
    id: str = "case_001",
    archetype: str = "clean_text",
    mock_scenario: str = "pass",
    expected_status: str = "pass",
    required_checks: tuple = (),
    metadata: dict | None = None,
) -> EvalCase:
    return EvalCase(
        id=id,
        archetype=archetype,
        graph_input={"raw_input": "some text"},
        mock_scenario=mock_scenario,
        expected_status=expected_status,
        required_checks=required_checks,
        metadata=metadata or {},
    )


def _make_dataset(cases: list[EvalCase] | None = None, version: str = "v1") -> EvalDataset:
    if cases is None:
        cases = [_make_case()]
    return EvalDataset(version=version, cases=tuple(cases))


def _make_thresholds(
    dataset_version: str = "v1",
    required_archetypes: tuple = ("clean_text",),
    minimum_pass_rate: float = 0.80,
    minimum_injection_resistance: float = 0.0,  # default 0 to avoid vacuous injection failure
    minimum_schema_validity: float = 1.0,
    max_cost_per_run_inr_exclusive: float = 50.0,
    max_average_cost_inr_inclusive: float = 25.0,
    offline_cost_per_call_inr: float = 2.0,
    pass_rate_archetypes: tuple | None = None,
    required_checks_all: tuple = (),
    required_checks_by_archetype: dict | None = None,
    injection_archetypes: tuple = (),
) -> EvalThresholds:
    if pass_rate_archetypes is None:
        pass_rate_archetypes = required_archetypes
    return EvalThresholds(
        dataset_version=dataset_version,
        required_archetypes=required_archetypes,
        minimum_pass_rate=minimum_pass_rate,
        pass_rate_archetypes=pass_rate_archetypes,
        minimum_injection_resistance=minimum_injection_resistance,
        minimum_schema_validity=minimum_schema_validity,
        max_cost_per_run_inr_exclusive=max_cost_per_run_inr_exclusive,
        max_average_cost_inr_inclusive=max_average_cost_inr_inclusive,
        offline_cost_per_call_inr=offline_cost_per_call_inr,
        required_checks_all=required_checks_all,
        required_checks_by_archetype=required_checks_by_archetype or {},
        injection_archetypes=injection_archetypes,
    )


def _make_obs(
    case_id: str = "case_001",
    terminal_status: str = "pass",
    cost_inr: float = 4.0,
    schema_valid: bool = True,
    check_results: dict | None = None,
) -> EvalObservation:
    # Default to expected_status=True so threshold-required check passes
    if check_results is None:
        check_results = {"expected_status": True}
    return EvalObservation(
        case_id=case_id,
        terminal_status=terminal_status,
        cost_inr=cost_inr,
        schema_valid=schema_valid,
        check_results=check_results,
    )


# ---------------------------------------------------------------------------
# 1. Valid round-trip
# ---------------------------------------------------------------------------

def test_valid_roundtrip_passes():
    dataset = _make_dataset()
    thresholds = _make_thresholds()
    obs = [_make_obs()]
    report = evaluate(dataset, obs, thresholds)
    assert report.passed
    assert report.total_cases == 1
    assert report.pass_rate == 1.0
    assert report.schema_validity_rate == 1.0


# ---------------------------------------------------------------------------
# 2. EvalDataset validation — duplicate IDs
# ---------------------------------------------------------------------------

def test_duplicate_case_ids_raises_validation_error():
    case1 = _make_case(id="dup", archetype="clean_text")
    case2 = _make_case(id="dup", archetype="messy_notes")
    with pytest.raises(ValidationError, match="Duplicate case IDs"):
        EvalDataset(version="v1", cases=(case1, case2))


# ---------------------------------------------------------------------------
# 3. EvalDataset validation — duplicate archetypes
# ---------------------------------------------------------------------------

def test_duplicate_archetypes_raises_validation_error():
    case1 = _make_case(id="c1", archetype="clean_text")
    case2 = _make_case(id="c2", archetype="clean_text")
    with pytest.raises(ValidationError, match="Duplicate archetypes"):
        EvalDataset(version="v1", cases=(case1, case2))


# ---------------------------------------------------------------------------
# 4. Version mismatch → failure in report (not ValueError)
# ---------------------------------------------------------------------------

def test_version_mismatch_produces_failure():
    dataset = _make_dataset(version="v1")
    thresholds = _make_thresholds(dataset_version="v2")
    obs = [_make_obs()]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("version mismatch" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 5. Missing required archetype → failure in report
# ---------------------------------------------------------------------------

def test_missing_required_archetype_produces_failure():
    dataset = _make_dataset(cases=[_make_case(archetype="clean_text")])
    thresholds = _make_thresholds(
        required_archetypes=("clean_text", "voice_transcript"),
        pass_rate_archetypes=("clean_text",),
    )
    obs = [_make_obs()]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("voice_transcript" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 6. Missing observation → failure in report
# ---------------------------------------------------------------------------

def test_missing_observation_produces_failure():
    case1 = _make_case(id="c1", archetype="clean_text")
    case2 = _make_case(id="c2", archetype="messy_notes")
    dataset = _make_dataset(cases=[case1, case2])
    thresholds = _make_thresholds(
        required_archetypes=("clean_text", "messy_notes"),
        pass_rate_archetypes=("clean_text",),
    )
    obs = [_make_obs(case_id="c1")]  # c2 missing
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("c2" in f and "missing" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 7. Extra observation (unknown case_id) → failure in report
# ---------------------------------------------------------------------------

def test_extra_observation_produces_failure():
    dataset = _make_dataset()
    thresholds = _make_thresholds()
    obs = [_make_obs(case_id="case_001"), _make_obs(case_id="unknown_case")]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("unknown_case" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 8. Duplicate observation → failure in report
# ---------------------------------------------------------------------------

def test_duplicate_observation_produces_failure():
    dataset = _make_dataset()
    thresholds = _make_thresholds()
    obs = [_make_obs(case_id="case_001"), _make_obs(case_id="case_001")]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("duplicate observation" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 9. Required check missing from observation.check_results → failure
# ---------------------------------------------------------------------------

def test_required_check_missing_from_check_results():
    case = _make_case(required_checks=("my_check",))
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds()
    obs = [_make_obs(check_results={"expected_status": True})]  # my_check not present
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("my_check" in f and "missing" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 10. Required check present but False → failure
# ---------------------------------------------------------------------------

def test_required_check_present_but_false():
    case = _make_case(required_checks=("my_check",))
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds()
    obs = [_make_obs(check_results={"expected_status": True, "my_check": False})]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("my_check" in f and "failed" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 11. Pass rate: 3/4 eligible → 0.75 < 0.80 → failure
# ---------------------------------------------------------------------------

def test_pass_rate_3_of_4_fails():
    cases = [
        _make_case(id=f"c{i}", archetype=f"arch{i}")
        for i in range(4)
    ]
    dataset = _make_dataset(cases=cases)
    thresholds = _make_thresholds(
        required_archetypes=tuple(f"arch{i}" for i in range(4)),
        minimum_pass_rate=0.80,
    )
    obs = [
        _make_obs(case_id="c0", terminal_status="pass"),
        _make_obs(case_id="c1", terminal_status="pass"),
        _make_obs(case_id="c2", terminal_status="pass"),
        _make_obs(case_id="c3", terminal_status="needs_human"),
    ]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert abs(report.pass_rate - 0.75) < 1e-9
    assert any("pass_rate" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 12. Pass rate: 4/4 eligible → 1.0 >= 0.80 → passes
# ---------------------------------------------------------------------------

def test_pass_rate_4_of_4_passes():
    cases = [
        _make_case(id=f"c{i}", archetype=f"arch{i}")
        for i in range(4)
    ]
    dataset = _make_dataset(cases=cases)
    thresholds = _make_thresholds(
        required_archetypes=tuple(f"arch{i}" for i in range(4)),
        minimum_pass_rate=0.80,
    )
    obs = [_make_obs(case_id=f"c{i}", terminal_status="pass") for i in range(4)]
    report = evaluate(dataset, obs, thresholds)
    assert report.pass_rate == 1.0
    assert not any("pass_rate" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 13. Pass rate: 0 eligible cases (no archetype in pass_rate_archetypes) → failure
# ---------------------------------------------------------------------------

def test_pass_rate_zero_eligible_cases_fails():
    # Use archetype "noneligible" which is in required_archetypes but NOT in pass_rate_archetypes
    case = _make_case(archetype="noneligible")
    dataset = _make_dataset(cases=[case])
    thresholds = EvalThresholds(
        dataset_version="v1",
        required_archetypes=("noneligible", "clean_text"),
        minimum_pass_rate=0.8,
        pass_rate_archetypes=("clean_text",),  # case archetype not here
        minimum_injection_resistance=0.0,
        minimum_schema_validity=0.0,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
        offline_cost_per_call_inr=2.0,
    )
    obs = [_make_obs()]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("no pass-rate-eligible" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 14. Schema validity rate: 1/2 valid → 0.5 < 1.0 → failure
# ---------------------------------------------------------------------------

def test_schema_validity_rate_1_of_2_fails():
    cases = [
        _make_case(id="c0", archetype="arch0"),
        _make_case(id="c1", archetype="arch1"),
    ]
    dataset = _make_dataset(cases=cases)
    thresholds = _make_thresholds(
        required_archetypes=("arch0", "arch1"),
        minimum_schema_validity=1.0,
    )
    obs = [
        _make_obs(case_id="c0", schema_valid=True),
        _make_obs(case_id="c1", schema_valid=False),
    ]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert abs(report.schema_validity_rate - 0.5) < 1e-9
    assert any("schema_validity" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 15. Injection resistance: 0/1 → failure; 1/1 → passes (uses injection_archetypes)
# ---------------------------------------------------------------------------

def test_injection_resistance_0_of_1_fails():
    case = _make_case(id="inj_001", archetype="prompt_injection")
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds(
        required_archetypes=("prompt_injection",),
        minimum_injection_resistance=1.0,
        injection_archetypes=("prompt_injection",),
    )
    obs = [_make_obs(case_id="inj_001", check_results={"expected_status": True, "injection_resisted": False})]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("injection_resistance" in f for f in report.failures)


def test_injection_resistance_1_of_1_passes():
    case = _make_case(id="inj_001", archetype="prompt_injection")
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds(
        required_archetypes=("prompt_injection",),
        minimum_injection_resistance=1.0,
        injection_archetypes=("prompt_injection",),
    )
    obs = [_make_obs(case_id="inj_001", check_results={"expected_status": True, "injection_resisted": True})]
    report = evaluate(dataset, obs, thresholds)
    assert report.injection_resistance_rate == 1.0
    assert not any("injection_resistance" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 16. Strict cost: cost == max_exclusive → fails (must be STRICTLY <)
# ---------------------------------------------------------------------------

def test_cost_equal_to_max_exclusive_fails():
    dataset = _make_dataset()
    thresholds = _make_thresholds(max_cost_per_run_inr_exclusive=50.0)
    obs = [_make_obs(cost_inr=50.0)]  # == exclusive ceiling → should FAIL
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("cost" in f.lower() for f in report.failures)


# ---------------------------------------------------------------------------
# 17. Strict cost: cost == max_exclusive - 0.001 → passes
# ---------------------------------------------------------------------------

def test_cost_just_under_exclusive_passes():
    dataset = _make_dataset()
    thresholds = _make_thresholds(max_cost_per_run_inr_exclusive=50.0)
    obs = [_make_obs(cost_inr=49.999)]  # strictly < 50 → should pass (cost check)
    report = evaluate(dataset, obs, thresholds)
    # No cost failure
    assert not any(">=" in f and "max_exclusive" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 18. Inclusive average: avg == max_inclusive → passes (<=)
# ---------------------------------------------------------------------------

def test_average_cost_equal_to_max_inclusive_passes():
    dataset = _make_dataset()
    thresholds = _make_thresholds(max_average_cost_inr_inclusive=25.0)
    obs = [_make_obs(cost_inr=25.0)]  # avg == 25.0 → should pass (<=)
    report = evaluate(dataset, obs, thresholds)
    assert not any("average" in f.lower() for f in report.failures)


# ---------------------------------------------------------------------------
# 19. Inclusive average: avg == max_inclusive + 0.001 → fails
# ---------------------------------------------------------------------------

def test_average_cost_just_over_max_inclusive_fails():
    dataset = _make_dataset()
    thresholds = _make_thresholds(max_average_cost_inr_inclusive=25.0)
    obs = [_make_obs(cost_inr=25.001)]  # avg > 25 → fails
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("average" in f.lower() for f in report.failures)


# ---------------------------------------------------------------------------
# 20. Negative threshold values → ValidationError on EvalThresholds
# ---------------------------------------------------------------------------

def test_negative_max_cost_raises():
    with pytest.raises(ValidationError):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=-1.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
        )


def test_negative_average_cost_raises():
    with pytest.raises(ValidationError):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=-1.0,
            offline_cost_per_call_inr=2.0,
        )


# ---------------------------------------------------------------------------
# 21. NaN threshold → ValidationError (allow_inf_nan=False on CoreContractModel)
# ---------------------------------------------------------------------------

def test_nan_min_pass_rate_raises():
    with pytest.raises(ValidationError):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=float("nan"),
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
        )


# ---------------------------------------------------------------------------
# 22. inf threshold → ValidationError
# ---------------------------------------------------------------------------

def test_inf_max_cost_raises():
    with pytest.raises(ValidationError):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=float("inf"),
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
        )


# ---------------------------------------------------------------------------
# 23. offline_cost_per_call_inr = 0 → ValidationError (must be > 0)
# ---------------------------------------------------------------------------

def test_offline_cost_zero_raises():
    with pytest.raises(ValidationError):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=0.0,  # must be > 0
        )


# ---------------------------------------------------------------------------
# 24. minimum_pass_rate > 1.0 → ValidationError
# ---------------------------------------------------------------------------

def test_pass_rate_above_1_raises():
    with pytest.raises(ValidationError):
        _make_thresholds(minimum_pass_rate=1.1)


# ---------------------------------------------------------------------------
# 25. minimum_pass_rate < 0.0 → ValidationError
# ---------------------------------------------------------------------------

def test_pass_rate_below_0_raises():
    with pytest.raises(ValidationError):
        _make_thresholds(minimum_pass_rate=-0.1)


# ---------------------------------------------------------------------------
# 26. Multiple failures all collected
# ---------------------------------------------------------------------------

def test_multiple_failures_all_collected():
    """Build a scenario with 3 independent failures; all 3 must appear in report.failures."""
    case1 = _make_case(id="c1", archetype="arch1")
    dataset = EvalDataset(version="v1", cases=(case1,))
    thresholds = EvalThresholds(
        dataset_version="v999",  # version mismatch → failure 1
        required_archetypes=("arch1", "arch_missing"),  # missing archetype → failure 2
        minimum_pass_rate=0.8,
        pass_rate_archetypes=("arch1",),
        minimum_injection_resistance=0.0,
        minimum_schema_validity=1.0,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
        offline_cost_per_call_inr=2.0,
    )
    obs = [_make_obs(case_id="c1", terminal_status="needs_human")]  # pass_rate 0 < 0.8 → failure 3
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert len(report.failures) >= 3
    assert any("version mismatch" in f for f in report.failures)
    assert any("arch_missing" in f for f in report.failures)
    assert any("pass_rate" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 27. assert_eval_report passes on clean report (no exception)
# ---------------------------------------------------------------------------

def test_assert_eval_report_passes_on_clean_report():
    dataset = _make_dataset()
    thresholds = _make_thresholds()
    obs = [_make_obs()]
    report = evaluate(dataset, obs, thresholds)
    assert report.passed
    assert_eval_report(report)  # must not raise


# ---------------------------------------------------------------------------
# 28. assert_eval_report raises AssertionError listing failures on bad report
# ---------------------------------------------------------------------------

def test_assert_eval_report_raises_on_failures():
    report = EvalReport(
        dataset_version="v1",
        total_cases=1,
        schema_validity_rate=1.0,
        pass_rate=0.0,
        injection_resistance_rate=1.0,
        average_cost_inr=0.0,
        max_cost_inr=0.0,
        failures=("failure_one", "failure_two"),
        passed=False,
    )
    with pytest.raises(AssertionError, match="failure_one"):
        assert_eval_report(report)


# ---------------------------------------------------------------------------
# 29. Deterministic: same inputs → same report
# ---------------------------------------------------------------------------

def test_deterministic_same_report():
    dataset = _make_dataset()
    thresholds = _make_thresholds()
    obs = [_make_obs()]
    report1 = evaluate(dataset, obs, thresholds)
    report2 = evaluate(dataset, obs, thresholds)
    assert report1.model_dump() == report2.model_dump()


# ---------------------------------------------------------------------------
# 30. load_dataset on malformed JSON → raises ValueError
# ---------------------------------------------------------------------------

def test_load_dataset_malformed_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not: valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to load dataset"):
        load_dataset(p)


# ---------------------------------------------------------------------------
# 31. load_dataset on missing required field → raises ValueError
# ---------------------------------------------------------------------------

def test_load_dataset_missing_required_field(tmp_path):
    p = tmp_path / "incomplete.json"
    p.write_text(json.dumps({"version": "v1"}), encoding="utf-8")  # missing "cases"
    with pytest.raises(ValueError, match="Dataset validation failed"):
        load_dataset(p)


# ---------------------------------------------------------------------------
# 32. load_thresholds on malformed YAML → raises ValueError
# ---------------------------------------------------------------------------

def test_load_thresholds_malformed_yaml(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("dataset_version: [unclosed", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to load thresholds"):
        load_thresholds(p)


# ---------------------------------------------------------------------------
# 33. Vacuous injection resistance — no injection-archetype cases → FAILS
# ---------------------------------------------------------------------------

def test_injection_resistance_fails_when_no_injection_cases():
    case = _make_case(archetype="clean_text")  # not in injection_archetypes
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds(
        minimum_injection_resistance=1.0,
        injection_archetypes=("prompt_injection",),
        required_archetypes=("clean_text", "prompt_injection"),
        pass_rate_archetypes=("clean_text",),
    )
    obs = [_make_obs()]
    report = evaluate(dataset, obs, thresholds)
    # Fails because injection-archetype case is missing from dataset
    assert not report.passed
    assert report.injection_resistance_rate == 0.0
    assert any("injection" in f.lower() for f in report.failures)


# ---------------------------------------------------------------------------
# 34. load_dataset valid file round-trips correctly
# ---------------------------------------------------------------------------

def test_load_dataset_valid_file(tmp_path):
    data = {
        "version": "test-v1",
        "cases": [
            {
                "id": "c1",
                "archetype": "clean_text",
                "graph_input": {"raw_input": "hello"},
                "mock_scenario": "pass",
                "expected_status": "pass",
                "required_checks": [],
                "metadata": {},
            }
        ],
    }
    p = tmp_path / "dataset.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ds = load_dataset(p)
    assert ds.version == "test-v1"
    assert len(ds.cases) == 1
    assert ds.cases[0].id == "c1"


# ---------------------------------------------------------------------------
# 35. load_thresholds valid file round-trips correctly
# ---------------------------------------------------------------------------

def test_load_thresholds_valid_file(tmp_path):
    content = (
        "dataset_version: test-v1\n"
        "required_archetypes:\n  - clean_text\n"
        "minimum_pass_rate: 0.80\n"
        "pass_rate_archetypes:\n  - clean_text\n"
        "minimum_injection_resistance: 0.0\n"  # 0.0 → injection_archetypes can be empty
        "minimum_schema_validity: 1.0\n"
        "max_cost_per_run_inr_exclusive: 50.0\n"
        "max_average_cost_inr_inclusive: 25.0\n"
        "offline_cost_per_call_inr: 2.0\n"
    )
    p = tmp_path / "thresholds.yaml"
    p.write_text(content, encoding="utf-8")
    t = load_thresholds(p)
    assert t.dataset_version == "test-v1"
    assert t.minimum_pass_rate == 0.80
    assert t.offline_cost_per_call_inr == 2.0


# ---------------------------------------------------------------------------
# 36. Required check present and True → no failure
# ---------------------------------------------------------------------------

def test_required_check_true_no_failure():
    case = _make_case(required_checks=("my_check",))
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds()
    obs = [_make_obs(check_results={"expected_status": True, "my_check": True})]
    report = evaluate(dataset, obs, thresholds)
    assert not any("my_check" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 37. EvalObservation cost_inr ge=0 validation
# ---------------------------------------------------------------------------

def test_eval_observation_negative_cost_raises():
    with pytest.raises(ValidationError):
        EvalObservation(
            case_id="c1",
            terminal_status="pass",
            cost_inr=-1.0,
            schema_valid=True,
        )


# ---------------------------------------------------------------------------
# 38. EvalCase with empty id raises
# ---------------------------------------------------------------------------

def test_eval_case_empty_id_raises():
    with pytest.raises(ValidationError):
        EvalCase(
            id="",
            archetype="clean_text",
            graph_input={"raw_input": "text"},
            mock_scenario="pass",
            expected_status="pass",
        )


# ---------------------------------------------------------------------------
# 39. EvalDataset extra field rejected (extra=forbid)
# ---------------------------------------------------------------------------

def test_eval_dataset_extra_field_rejected():
    with pytest.raises(ValidationError):
        EvalDataset(version="v1", cases=(), unknown_field="oops")


# ---------------------------------------------------------------------------
# 40. EvalReport fields computed correctly in valid scenario
# ---------------------------------------------------------------------------

def test_eval_report_fields():
    cases = [
        _make_case(id="c1", archetype="arch1"),
        _make_case(id="c2", archetype="arch2"),
    ]
    dataset = _make_dataset(cases=cases)
    thresholds = _make_thresholds(
        required_archetypes=("arch1", "arch2"),
        minimum_pass_rate=0.5,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
    )
    obs = [
        _make_obs(case_id="c1", terminal_status="pass", cost_inr=10.0),
        _make_obs(case_id="c2", terminal_status="pass", cost_inr=20.0),
    ]
    report = evaluate(dataset, obs, thresholds)
    assert report.total_cases == 2
    assert report.pass_rate == 1.0
    assert report.average_cost_inr == 15.0
    assert report.max_cost_inr == 20.0
    assert report.passed


# ---------------------------------------------------------------------------
# Issue 1 — Pass rate uses thresholds archetypes, not dataset field
# ---------------------------------------------------------------------------

def test_pass_rate_uses_thresholds_archetypes_not_dataset_field():
    """Archetype 'b' cases passing cannot inflate pass-rate — only archetype 'a' is in threshold."""
    # 2 cases archetype='b' (pass), 1 case archetype='a' (fail)
    case_a = _make_case(id="a_001", archetype="a")
    case_b1 = _make_case(id="b_001", archetype="b")
    case_b2 = _make_case(id="b_002", archetype="b2")
    dataset = EvalDataset(version="v1", cases=(case_a, case_b1, case_b2))
    thresholds = EvalThresholds(
        dataset_version="v1",
        required_archetypes=("a", "b", "b2"),
        minimum_pass_rate=0.5,
        pass_rate_archetypes=("a",),  # only 'a' counts for pass rate
        minimum_injection_resistance=0.0,
        minimum_schema_validity=0.0,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
        offline_cost_per_call_inr=2.0,
    )
    obs = [
        _make_obs(case_id="a_001", terminal_status="needs_human"),  # fails
        _make_obs(case_id="b_001", terminal_status="pass"),         # passes but ineligible
        _make_obs(case_id="b_002", terminal_status="pass"),         # passes but ineligible
    ]
    report = evaluate(dataset, obs, thresholds)
    # Only case 'a' is eligible → 0/1 = 0% < 50%
    assert not report.passed
    assert abs(report.pass_rate - 0.0) < 1e-9
    assert any("pass_rate" in f for f in report.failures)


def test_pass_rate_archetypes_not_subset_of_required_raises():
    """pass_rate_archetypes containing 'x' not in required_archetypes → ValidationError."""
    with pytest.raises(ValidationError, match="not in required_archetypes"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text", "x"),  # 'x' not in required
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
        )


def test_pass_rate_archetypes_duplicates_raises():
    """pass_rate_archetypes with duplicates → ValidationError."""
    with pytest.raises(ValidationError, match="duplicates"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text", "clean_text"),  # duplicate
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
        )


def test_pass_rate_archetypes_empty_raises():
    """pass_rate_archetypes empty → ValidationError."""
    with pytest.raises(ValidationError, match="non-empty"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=(),  # empty
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
        )


# ---------------------------------------------------------------------------
# Issue 1 — Config-based required_checks_all fires even with empty required_checks
# ---------------------------------------------------------------------------

def test_required_checks_all_fires_even_without_dataset_required_checks():
    """required_checks_all fires for every case even when dataset required_checks=[]."""
    case = _make_case(id="c1", archetype="clean_text", required_checks=())
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds(
        required_checks_all=("expected_status",),
    )
    # expected_status missing → threshold-required check fires
    obs = [_make_obs(case_id="c1", check_results={})]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("expected_status" in f and "threshold-required" in f for f in report.failures)


def test_required_checks_by_archetype_fires_for_matching_archetype():
    """required_checks_by_archetype fires for matching archetype even when required_checks=[]."""
    case = _make_case(id="inj", archetype="prompt_injection", required_checks=())
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds(
        required_archetypes=("prompt_injection",),
        required_checks_by_archetype={"prompt_injection": ["injection_resisted"]},
        minimum_injection_resistance=0.0,
    )
    obs = [_make_obs(case_id="inj", check_results={"expected_status": True})]  # injection_resisted missing
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("injection_resisted" in f and "threshold-required" in f for f in report.failures)


def test_required_checks_by_archetype_does_not_fire_for_other_archetypes():
    """required_checks_by_archetype only fires for its own archetype."""
    case = _make_case(id="c1", archetype="clean_text", required_checks=())
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds(
        required_archetypes=("clean_text",),
        required_checks_by_archetype={"clean_text": ["expected_status"]},
    )
    obs = [_make_obs(case_id="c1", check_results={"expected_status": True})]
    report = evaluate(dataset, obs, thresholds)
    assert report.passed


def test_required_checks_all_and_by_archetype_combined():
    """Both required_checks_all and archetype-specific checks can fire together."""
    case = _make_case(id="inj", archetype="prompt_injection", required_checks=())
    dataset = _make_dataset(cases=[case])
    thresholds = _make_thresholds(
        required_archetypes=("prompt_injection",),
        required_checks_all=("expected_status",),
        required_checks_by_archetype={"prompt_injection": ["injection_resisted"]},
        minimum_injection_resistance=0.0,
    )
    # Both checks missing
    obs = [_make_obs(case_id="inj", check_results={})]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    failure_text = " ".join(report.failures)
    assert "expected_status" in failure_text
    assert "injection_resisted" in failure_text


# ---------------------------------------------------------------------------
# Issue 1 — injection_archetypes validation
# ---------------------------------------------------------------------------

def test_injection_archetypes_unknown_archetype_raises():
    """injection_archetypes containing archetype not in required_archetypes → ValidationError."""
    with pytest.raises(ValidationError, match="not in required_archetypes"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
            injection_archetypes=("unknown_arch",),  # not in required_archetypes
        )


def test_injection_archetypes_empty_with_nonzero_threshold_raises():
    """injection_archetypes empty when minimum_injection_resistance > 0 → ValidationError."""
    with pytest.raises(ValidationError, match="injection_archetypes must be non-empty"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=1.0,  # > 0 requires injection_archetypes
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
            injection_archetypes=(),  # empty → error
        )


def test_injection_archetypes_duplicates_raises():
    """injection_archetypes with duplicates → ValidationError."""
    with pytest.raises(ValidationError, match="injection_archetypes has duplicates"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text", "prompt_injection"),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
            injection_archetypes=("prompt_injection", "prompt_injection"),  # duplicate
        )


def test_injection_archetypes_valid_no_error():
    """Valid injection_archetypes with matching required_archetypes → no error."""
    t = EvalThresholds(
        dataset_version="v1",
        required_archetypes=("clean_text", "prompt_injection"),
        minimum_pass_rate=0.8,
        pass_rate_archetypes=("clean_text",),
        minimum_injection_resistance=1.0,
        minimum_schema_validity=1.0,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
        offline_cost_per_call_inr=2.0,
        injection_archetypes=("prompt_injection",),
    )
    assert t.injection_archetypes == ("prompt_injection",)


# ---------------------------------------------------------------------------
# Issue 1 — required_checks_by_archetype validation
# ---------------------------------------------------------------------------

def test_required_checks_by_archetype_unknown_archetype_raises():
    """required_checks_by_archetype with unknown archetype → ValidationError."""
    with pytest.raises(ValidationError, match="unknown archetype"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
            required_checks_by_archetype={"unknown_arch": ["some_check"]},
        )


def test_required_checks_all_empty_check_name_raises():
    """required_checks_all with empty check name → ValidationError."""
    with pytest.raises(ValidationError, match="check name"):
        EvalThresholds(
            dataset_version="v1",
            required_archetypes=("clean_text",),
            minimum_pass_rate=0.8,
            pass_rate_archetypes=("clean_text",),
            minimum_injection_resistance=0.0,
            minimum_schema_validity=1.0,
            max_cost_per_run_inr_exclusive=50.0,
            max_average_cost_inr_inclusive=25.0,
            offline_cost_per_call_inr=2.0,
            required_checks_all=("",),  # empty check name
        )


def test_required_checks_by_archetype_valid_all_matching():
    """Valid required_checks_by_archetype with matching archetypes → no error."""
    t = EvalThresholds(
        dataset_version="v1",
        required_archetypes=("clean_text", "prompt_injection"),
        minimum_pass_rate=0.8,
        pass_rate_archetypes=("clean_text",),
        minimum_injection_resistance=0.0,
        minimum_schema_validity=1.0,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
        offline_cost_per_call_inr=2.0,
        required_checks_by_archetype={"prompt_injection": ["injection_resisted", "expected_status"]},
    )
    from evals.harness import _deep_unfreeze
    rcba = _deep_unfreeze(t.required_checks_by_archetype)
    assert rcba["prompt_injection"] == ["injection_resisted", "expected_status"]


# ---------------------------------------------------------------------------
# Issue 1 — Dataset extra archetypes not in required_archetypes → failure
# ---------------------------------------------------------------------------

def test_dataset_extra_archetype_produces_failure():
    """Dataset with archetype not in required_archetypes → failure in report."""
    case = _make_case(id="c1", archetype="unexpected_arch")
    dataset = _make_dataset(cases=[case])
    thresholds = EvalThresholds(
        dataset_version="v1",
        required_archetypes=("clean_text",),  # unexpected_arch NOT listed
        minimum_pass_rate=0.8,
        pass_rate_archetypes=("clean_text",),
        minimum_injection_resistance=0.0,
        minimum_schema_validity=0.0,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
        offline_cost_per_call_inr=2.0,
    )
    obs = [_make_obs(case_id="c1")]
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("unexpected_arch" in f for f in report.failures)


# ---------------------------------------------------------------------------
# Issue 4 — EvalReport consistency invariant
# ---------------------------------------------------------------------------

def test_eval_report_passed_true_with_failures_raises():
    """EvalReport with passed=True but non-empty failures → ValidationError."""
    with pytest.raises(ValidationError):
        EvalReport(
            dataset_version="v1", total_cases=1,
            schema_validity_rate=1.0, pass_rate=1.0,
            injection_resistance_rate=1.0, average_cost_inr=1.0, max_cost_inr=1.0,
            failures=("some failure",),
            passed=True,  # inconsistent
        )


def test_eval_report_passed_false_with_no_failures_raises():
    """EvalReport with passed=False but empty failures → ValidationError."""
    with pytest.raises(ValidationError):
        EvalReport(
            dataset_version="v1", total_cases=1,
            schema_validity_rate=1.0, pass_rate=1.0,
            injection_resistance_rate=1.0, average_cost_inr=1.0, max_cost_inr=1.0,
            failures=(),
            passed=False,  # inconsistent
        )


def test_assert_eval_report_catches_failures_even_if_passed_true():
    """assert_eval_report catches failures even when model_construct bypasses validator."""
    # Use model_construct to bypass the invariant validator
    report = EvalReport.model_construct(
        dataset_version="v1", total_cases=1,
        schema_validity_rate=1.0, pass_rate=1.0,
        injection_resistance_rate=1.0, average_cost_inr=1.0, max_cost_inr=1.0,
        failures=("tampered failure",),
        passed=True,  # bypassed
    )
    with pytest.raises(AssertionError, match="tampered failure"):
        assert_eval_report(report)


# ---------------------------------------------------------------------------
# Issue 2 — Immutability: checkpoint-safe FrozenJsonDict (no MappingProxyType)
# ---------------------------------------------------------------------------

def test_eval_case_graph_input_immutable():
    """graph_input cannot be mutated after construction (FrozenJsonDict raises TypeError)."""
    case = EvalCase(
        id="test", archetype="clean_text",
        graph_input={"raw_input": "hello"},
        mock_scenario="pass", expected_status="pass",
        required_checks=(),
    )
    with pytest.raises(TypeError):
        case.graph_input["raw_input"] = "mutated"


def test_eval_case_metadata_immutable():
    """metadata cannot be mutated after construction."""
    case = EvalCase(
        id="test", archetype="clean_text",
        graph_input={"raw_input": "hello"},
        mock_scenario="pass", expected_status="pass",
        metadata={"key": "value"},
    )
    with pytest.raises(TypeError):
        case.metadata["key"] = "mutated"


def test_eval_observation_check_results_immutable():
    """check_results cannot be mutated after construction."""
    obs = EvalObservation(
        case_id="test", terminal_status="pass",
        cost_inr=1.0, schema_valid=True,
        check_results={"expected_status": True},
    )
    with pytest.raises(TypeError):
        obs.check_results["expected_status"] = False


def test_eval_case_model_dump_returns_plain_dict():
    """model_dump() returns regular dicts, not FrozenJsonDict."""
    case = EvalCase(
        id="test", archetype="clean_text",
        graph_input={"raw_input": "hello"},
        mock_scenario="pass", expected_status="pass",
    )
    d = case.model_dump()
    assert isinstance(d["graph_input"], dict)
    assert d["graph_input"]["raw_input"] == "hello"


def test_eval_observation_model_dump_returns_plain_dicts():
    """model_dump() on EvalObservation returns regular dicts."""
    obs = EvalObservation(
        case_id="test", terminal_status="pass",
        cost_inr=1.0, schema_valid=True,
        check_results={"expected_status": True},
        recorded_messages=({"role": "user", "content": "hi"},),
    )
    d = obs.model_dump()
    assert isinstance(d["check_results"], dict)
    assert isinstance(d["recorded_messages"][0], dict)


def test_eval_case_model_copy_deep_works():
    """model_copy(deep=True) works on EvalCase with FrozenJsonDict fields."""
    case = EvalCase(
        id="test", archetype="clean_text",
        graph_input={"raw_input": "hello"},
        mock_scenario="pass", expected_status="pass",
        metadata={"key": "value"},
    )
    case2 = case.model_copy(deep=True)
    assert case2.id == case.id
    from evals.harness import _deep_unfreeze
    assert _deep_unfreeze(case2.graph_input) == {"raw_input": "hello"}
    assert _deep_unfreeze(case2.metadata) == {"key": "value"}


def test_eval_case_pickle_roundtrip():
    """EvalCase can be pickled and unpickled (checkpoint-safe)."""
    case = EvalCase(
        id="test", archetype="clean_text",
        graph_input={"raw_input": "hello", "nested": [1, 2, 3]},
        mock_scenario="pass", expected_status="pass",
        metadata={"key": "value"},
    )
    case2 = pickle.loads(pickle.dumps(case))
    assert case2.id == case.id
    # After unpickle, mutation should still fail
    with pytest.raises(TypeError):
        case2.graph_input["raw_input"] = "mutated"


def test_eval_case_set_rejected():
    """Sets in graph_input are rejected by the validator."""
    with pytest.raises((ValidationError, Exception)):
        EvalCase(
            id="test", archetype="clean_text",
            graph_input={"key": {1, 2, 3}},  # set → rejected
            mock_scenario="pass", expected_status="pass",
        )


def test_eval_case_non_string_key_rejected():
    """Non-string keys in graph_input are rejected."""
    with pytest.raises((ValidationError, Exception)):
        EvalCase(
            id="test", archetype="clean_text",
            graph_input={1: "value"},  # integer key → rejected
            mock_scenario="pass", expected_status="pass",
        )


def test_eval_case_nan_in_graph_input_rejected():
    """NaN float values in graph_input are rejected."""
    with pytest.raises((ValidationError, Exception)):
        EvalCase(
            id="test", archetype="clean_text",
            graph_input={"val": float("nan")},
            mock_scenario="pass", expected_status="pass",
        )


def test_eval_case_nested_list_becomes_immutable():
    """Nested lists in graph_input become tuples (immutable)."""
    case = EvalCase(
        id="test", archetype="clean_text",
        graph_input={"items": [1, 2, 3]},
        mock_scenario="pass", expected_status="pass",
    )
    # The items value should be a tuple (immutable)
    assert isinstance(case.graph_input["items"], tuple)
    # Mutation should fail
    with pytest.raises(TypeError):
        case.graph_input["items"][0] = 99


def test_eval_case_model_dump_json_returns_list_not_tuple():
    """model_dump(mode='json') returns lists, not tuples, for sequence fields."""
    case = EvalCase(
        id="test", archetype="clean_text",
        graph_input={"items": [1, 2, 3]},
        mock_scenario="pass", expected_status="pass",
    )
    d = case.model_dump(mode="json")
    assert isinstance(d["graph_input"]["items"], list)
    assert d["graph_input"]["items"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Issue 1 (Increment 4 repair) — check_results strict bool validation
# ---------------------------------------------------------------------------

def test_check_results_string_value_rejected():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                        schema_valid=True, check_results={"expected_status": "yes"})


def test_check_results_integer_value_rejected():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                        schema_valid=True, check_results={"expected_status": 1})


def test_check_results_list_type_rejected():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                        schema_valid=True, check_results=[])


def test_check_results_bool_type_rejected():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                        schema_valid=True, check_results=True)


def test_check_results_empty_key_rejected():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                        schema_valid=True, check_results={"": True})


def test_check_results_strict_bool_true_accepted():
    from evals.harness import _deep_unfreeze
    obs = EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                          schema_valid=True, check_results={"expected_status": True})
    assert _deep_unfreeze(obs.check_results)["expected_status"] is True


def test_check_results_strict_bool_false_accepted():
    from evals.harness import _deep_unfreeze
    obs = EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                          schema_valid=True, check_results={"expected_status": False})
    assert _deep_unfreeze(obs.check_results)["expected_status"] is False


def test_check_results_immutable():
    obs = EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                          schema_valid=True, check_results={"expected_status": True})
    with pytest.raises((TypeError, AttributeError)):
        obs.check_results["expected_status"] = False


# ---------------------------------------------------------------------------
# Minimal helpers for Issues 1/2/3 tests (low-overhead, self-contained)
# ---------------------------------------------------------------------------

def _make_minimal_thresholds(
    version="v1",
    required_archetypes=("clean_text",),
    pass_rate_archetypes=("clean_text",),
    minimum_pass_rate=0.0,
    injection_archetypes=(),
    minimum_injection_resistance=0.0,
):
    return EvalThresholds(
        dataset_version=version,
        required_archetypes=required_archetypes,
        minimum_pass_rate=minimum_pass_rate,
        pass_rate_archetypes=pass_rate_archetypes,
        minimum_injection_resistance=minimum_injection_resistance,
        minimum_schema_validity=0.0,
        max_cost_per_run_inr_exclusive=50.0,
        max_average_cost_inr_inclusive=25.0,
        offline_cost_per_call_inr=2.0,
        required_checks_all=(),
        required_checks_by_archetype={},
        injection_archetypes=injection_archetypes,
    )


def _make_minimal_case(
    case_id="c1",
    archetype="clean_text",
    expected_status="pass",
    required_checks=(),
):
    return EvalCase(
        id=case_id,
        archetype=archetype,
        graph_input={"raw_input": "test"},
        mock_scenario="pass",
        expected_status=expected_status,
        required_checks=required_checks,
    )


def _make_minimal_obs(
    case_id="c1",
    terminal_status="pass",
    schema_valid=True,
    check_results=None,
    cost_inr=1.0,
):
    return EvalObservation(
        case_id=case_id,
        terminal_status=terminal_status,
        cost_inr=cost_inr,
        schema_valid=schema_valid,
        check_results=check_results if check_results is not None else {"expected_status": True},
    )


# ---------------------------------------------------------------------------
# Issue 1 — Direct terminal-status enforcement (cannot be spoofed)
# ---------------------------------------------------------------------------

def test_mismatched_terminal_status_fails_even_with_spoofed_check():
    """Direct terminal-status check cannot be bypassed by expected_status=True in check_results."""
    dataset = EvalDataset(
        version="v1",
        cases=(_make_minimal_case(expected_status="needs_human"),)
    )
    thresholds = _make_minimal_thresholds()
    obs = [_make_minimal_obs(terminal_status="pass",  # mismatch: expected "needs_human"
                             check_results={"expected_status": True})]  # spoofed
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("terminal_status" in f and "needs_human" in f for f in report.failures), (
        f"Expected terminal_status failure, got: {report.failures}"
    )


def test_mismatched_terminal_status_error_scenario():
    """Expected 'pass', observed 'error', spoofed check still fails."""
    dataset = EvalDataset(
        version="v1",
        cases=(_make_minimal_case(expected_status="pass"),)
    )
    thresholds = _make_minimal_thresholds()
    obs = [_make_minimal_obs(terminal_status="error",  # mismatch: expected "pass"
                             check_results={"expected_status": True})]  # spoofed
    report = evaluate(dataset, obs, thresholds)
    assert not report.passed
    assert any("terminal_status" in f and "error" in f for f in report.failures), (
        f"Expected terminal_status failure, got: {report.failures}"
    )


def test_matching_terminal_status_passes():
    """Matching status passes the direct check."""
    dataset = EvalDataset(
        version="v1",
        cases=(_make_minimal_case(expected_status="pass"),)
    )
    thresholds = _make_minimal_thresholds()
    obs = [_make_minimal_obs(terminal_status="pass",
                             check_results={"expected_status": True})]
    report = evaluate(dataset, obs, thresholds)
    assert not any("terminal_status" in f for f in report.failures), (
        f"Unexpected terminal_status failure: {report.failures}"
    )


def test_spoofed_expected_status_check_cannot_suppress_direct_failure():
    """check_results['expected_status']=True does not suppress a status mismatch in failures."""
    dataset = EvalDataset(
        version="v1",
        cases=(_make_minimal_case(expected_status="needs_human"),)
    )
    thresholds = _make_minimal_thresholds()
    obs = [_make_minimal_obs(terminal_status="pass",
                             check_results={"expected_status": True})]  # spoofed True
    report = evaluate(dataset, obs, thresholds)
    # The direct comparison must have added a terminal_status failure
    assert any("terminal_status" in f for f in report.failures), (
        f"Spoofed check_results should not suppress terminal_status failure: {report.failures}"
    )
    assert not report.passed


# ---------------------------------------------------------------------------
# Issue 2 — StrictBool on schema_valid and EvalReport.passed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_value", ["yes", "true", "false", "1", "0", 1, 0, 1.0, 0.0, None])
def test_schema_valid_rejects_non_strict_bool(bad_value):
    with pytest.raises(ValidationError):
        EvalObservation(
            case_id="t", terminal_status="pass", cost_inr=0.0,
            schema_valid=bad_value,
            check_results={},
        )


def test_schema_valid_accepts_true():
    obs = EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                          schema_valid=True, check_results={})
    assert obs.schema_valid is True


def test_schema_valid_accepts_false():
    obs = EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                          schema_valid=False, check_results={})
    assert obs.schema_valid is False


@pytest.mark.parametrize("bad_value", ["yes", "true", "false", "1", "0", 1, 0, 1.0, 0.0, None])
def test_eval_report_passed_rejects_non_strict_bool(bad_value):
    with pytest.raises(ValidationError):
        EvalReport(
            dataset_version="v1", total_cases=1,
            schema_validity_rate=1.0, pass_rate=1.0,
            injection_resistance_rate=1.0, average_cost_inr=1.0, max_cost_inr=1.0,
            failures=(),
            passed=bad_value,
        )


# ---------------------------------------------------------------------------
# Issue 3 — Whitespace-only identifier rejection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,kwargs", [
    ("id", {"id": "  ", "archetype": "clean_text", "graph_input": {}, "mock_scenario": "pass", "expected_status": "pass"}),
    ("archetype", {"id": "t", "archetype": "   ", "graph_input": {}, "mock_scenario": "pass", "expected_status": "pass"}),
    ("mock_scenario", {"id": "t", "archetype": "clean_text", "graph_input": {}, "mock_scenario": " ", "expected_status": "pass"}),
    ("expected_status", {"id": "t", "archetype": "clean_text", "graph_input": {}, "mock_scenario": "pass", "expected_status": "\t"}),
])
def test_eval_case_rejects_whitespace_only_identifiers(field, kwargs):
    with pytest.raises(ValidationError):
        EvalCase(**kwargs)


def test_eval_case_rejects_blank_required_check():
    with pytest.raises(ValidationError):
        EvalCase(id="t", archetype="a", graph_input={}, mock_scenario="pass",
                 expected_status="pass", required_checks=("  ",))


def test_eval_observation_rejects_whitespace_only_case_id():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="  ", terminal_status="pass", cost_inr=0.0,
                        schema_valid=True, check_results={})


def test_eval_observation_rejects_whitespace_only_terminal_status():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="t", terminal_status="  ", cost_inr=0.0,
                        schema_valid=True, check_results={})


def test_check_results_rejects_whitespace_only_key():
    with pytest.raises(ValidationError):
        EvalObservation(case_id="t", terminal_status="pass", cost_inr=0.0,
                        schema_valid=True, check_results={"  ": True})
