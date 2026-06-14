from __future__ import annotations

from pathlib import Path

import pytest

from evals import assert_eval_report, evaluate, load_dataset, load_thresholds
from evals.harness import _deep_unfreeze

from .adapter import load_cfg, run_case


_DATASET_PATH = Path(__file__).parent / "cases.v1.json"
_THRESHOLDS_PATH = Path(__file__).parent / "thresholds.yaml"


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(_DATASET_PATH)


@pytest.fixture(scope="module")
def thresholds():
    return load_thresholds(_THRESHOLDS_PATH)


@pytest.fixture(scope="module")
def cfg():
    return load_cfg()


@pytest.fixture(scope="module")
def observations(dataset, cfg):
    return {case.id: run_case(case, cfg) for case in dataset.cases}


@pytest.fixture(scope="module")
def report(dataset, observations, thresholds):
    return evaluate(dataset, list(observations.values()), thresholds)


@pytest.mark.parametrize(
    "case_id",
    [
        "clean_blog_001",
        "long_technical_blog_001",
        "weak_cta_001",
        "generic_boring_source_001",
        "multi_platform_newsletter_001",
        "source_prompt_injection_001",
        "confidential_internal_source_001",
        "thin_input_001",
        "llm_authored_001",
    ],
)
def test_eval_case_required_checks(case_id, dataset, observations) -> None:
    case = next(item for item in dataset.cases if item.id == case_id)
    observation = observations[case_id]
    checks = _deep_unfreeze(observation.check_results)

    assert observation.schema_valid
    assert observation.terminal_status == case.expected_status
    for check_name in case.required_checks:
        assert checks.get(check_name), f"{case_id}: {check_name} failed"


def test_eval_report_passes(report) -> None:
    assert_eval_report(report)


def test_quality_thresholds_are_met_for_pass_cases(dataset, observations) -> None:
    for case in dataset.cases:
        if case.expected_status != "pass":
            continue
        checks = _deep_unfreeze(observations[case.id].check_results)
        assert checks.get("quality_score_min"), case.id
        assert checks.get("cta_clarity_min", True), case.id
        assert checks.get("cost_under_30"), case.id


def test_adversarial_cases_detect_terminal_failures(observations) -> None:
    for case_id in ("source_prompt_injection_001", "confidential_internal_source_001"):
        checks = _deep_unfreeze(observations[case_id].check_results)
        assert checks["terminal_hard_fail_detected"]


def test_eval_determinism(dataset, cfg) -> None:
    first = {case.id: run_case(case, cfg).model_dump() for case in dataset.cases}
    second = {case.id: run_case(case, cfg).model_dump() for case in dataset.cases}
    assert first == second
