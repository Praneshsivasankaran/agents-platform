from __future__ import annotations

import json
from pathlib import Path

import yaml


EVAL_DIR = Path(__file__).resolve().parent


def test_eval_cases_and_thresholds_are_well_formed() -> None:
    cases = json.loads((EVAL_DIR / "cases.v1.json").read_text(encoding="utf-8"))
    thresholds = yaml.safe_load((EVAL_DIR / "thresholds.yaml").read_text(encoding="utf-8"))

    assert len(cases) == 8
    assert thresholds["pass_threshold"] == 80
    required_metrics = set(thresholds["metrics"])
    for case in cases:
        assert case["id"]
        assert set(case["expected"]).issubset(required_metrics)
