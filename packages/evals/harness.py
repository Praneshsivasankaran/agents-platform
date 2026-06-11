"""Agent-agnostic offline eval harness — models, loaders, evaluator."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from pydantic import Field, StrictBool, field_serializer, field_validator, model_validator

from core.interfaces.base import CoreContractModel, _to_frozen_json, _json_thaw

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Checkpoint-safe immutable JSON helpers (re-exported for adapter use)
# ---------------------------------------------------------------------------

def _deep_freeze(value: Any) -> Any:
    """Validate and deeply freeze a JSON-compatible value using the core FrozenJsonDict pattern.

    Accepts: None, bool, int, finite float, str, str-keyed dicts, lists/tuples.
    Rejects: sets, bytes, Pydantic models, arbitrary objects, non-string keys, NaN, inf.
    Returns a deeply immutable value (FrozenJsonDict for mappings, tuple for sequences).
    Pickle-safe, model_copy(deep=True)-safe, checkpoint-safe.
    """
    return _to_frozen_json(value)


def _deep_unfreeze(value: Any) -> Any:
    """Convert frozen JSON value back to plain dict/list for serialization and graph invocation."""
    return _json_thaw(value)


class EvalCase(CoreContractModel):
    id: str = Field(min_length=1)
    archetype: str = Field(min_length=1)
    graph_input: Any  # FrozenJsonDict after construction
    mock_scenario: str = Field(min_length=1)
    expected_status: str = Field(min_length=1)
    required_checks: tuple[str, ...] = ()
    metadata: Any = Field(default_factory=dict)

    @field_validator("id", "archetype", "mock_scenario", "expected_status", mode="after")
    @classmethod
    def _no_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(f"value must not be whitespace-only, got {v!r}")
        return v  # do NOT strip — reject, don't normalize

    @field_validator("required_checks", mode="after")
    @classmethod
    def _no_blank_required_checks(cls, v: tuple) -> tuple:
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"required_checks entry must be non-blank string, got {item!r}")
        return v

    @model_validator(mode="after")
    def _freeze_mutable_fields(self) -> "EvalCase":
        object.__setattr__(self, "graph_input", _deep_freeze(self.graph_input))
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))
        return self

    @field_serializer("graph_input", "metadata")
    def _serialize_frozen(self, v: Any) -> Any:
        return _deep_unfreeze(v)


class EvalDataset(CoreContractModel):
    version: str = Field(min_length=1)
    cases: tuple[EvalCase, ...]

    @model_validator(mode="after")
    def _no_duplicate_ids(self) -> "EvalDataset":
        ids = [c.id for c in self.cases]
        dupes = sorted({x for x in ids if ids.count(x) > 1})
        if dupes:
            raise ValueError(f"Duplicate case IDs: {dupes}")
        return self

    @model_validator(mode="after")
    def _no_duplicate_archetypes(self) -> "EvalDataset":
        archetypes = [c.archetype for c in self.cases]
        dupes = sorted({x for x in archetypes if archetypes.count(x) > 1})
        if dupes:
            raise ValueError(f"Duplicate archetypes: {dupes}")
        return self


class EvalThresholds(CoreContractModel):
    dataset_version: str = Field(min_length=1)
    required_archetypes: tuple[str, ...]
    minimum_pass_rate: float = Field(ge=0.0, le=1.0)
    pass_rate_archetypes: tuple[str, ...]
    minimum_injection_resistance: float = Field(ge=0.0, le=1.0)
    minimum_schema_validity: float = Field(ge=0.0, le=1.0)
    max_cost_per_run_inr_exclusive: float
    max_average_cost_inr_inclusive: float
    offline_cost_per_call_inr: float = Field(gt=0.0)

    # Issue 1 — Agent-agnostic archetype/check policy (replaces _ARCHETYPE_REQUIRED_CHECKS)
    required_checks_all: tuple[str, ...] = ()
    required_checks_by_archetype: Any = Field(default_factory=dict)  # FrozenJsonDict after construction
    injection_archetypes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _freeze_rcba(self) -> "EvalThresholds":
        """Freeze required_checks_by_archetype to a FrozenJsonDict."""
        object.__setattr__(
            self, "required_checks_by_archetype",
            _deep_freeze(self.required_checks_by_archetype)
        )
        return self

    @field_serializer("required_checks_by_archetype")
    def _serialize_rcba(self, v: Any) -> Any:
        return _deep_unfreeze(v)

    @model_validator(mode="after")
    def _finite_cost_thresholds(self) -> "EvalThresholds":
        for name, val in [
            ("max_cost_per_run_inr_exclusive", self.max_cost_per_run_inr_exclusive),
            ("max_average_cost_inr_inclusive", self.max_average_cost_inr_inclusive),
        ]:
            if not math.isfinite(val) or val < 0:
                raise ValueError(f"{name} must be finite and non-negative, got {val}")
        return self

    @model_validator(mode="after")
    def _validate_pass_rate_archetypes(self) -> "EvalThresholds":
        pra = list(self.pass_rate_archetypes)
        if not pra:
            raise ValueError("pass_rate_archetypes must be non-empty")
        dupes = sorted({x for x in pra if pra.count(x) > 1})
        if dupes:
            raise ValueError(f"pass_rate_archetypes has duplicates: {dupes}")
        required_set = set(self.required_archetypes)
        not_in_required = [a for a in pra if a not in required_set]
        if not_in_required:
            raise ValueError(
                f"pass_rate_archetypes contains archetypes not in required_archetypes: "
                f"{not_in_required}"
            )
        return self

    @model_validator(mode="after")
    def _validate_archetype_policy(self) -> "EvalThresholds":
        required_set = set(self.required_archetypes)

        if not required_set:
            raise ValueError("required_archetypes must not be empty")

        # Duplicate required_archetypes
        ras = list(self.required_archetypes)
        dupes = sorted({x for x in ras if ras.count(x) > 1})
        if dupes:
            raise ValueError(f"required_archetypes has duplicates: {dupes}")

        # injection_archetypes validation
        inj_list = list(self.injection_archetypes)
        inj_dupes = sorted({x for x in inj_list if inj_list.count(x) > 1})
        if inj_dupes:
            raise ValueError(f"injection_archetypes has duplicates: {inj_dupes}")
        if self.minimum_injection_resistance > 0 and not self.injection_archetypes:
            raise ValueError(
                "injection_archetypes must be non-empty when minimum_injection_resistance > 0"
            )
        for arch in self.injection_archetypes:
            if arch not in required_set:
                raise ValueError(
                    f"injection_archetypes contains {arch!r} which is not in required_archetypes"
                )

        # required_checks_by_archetype validation (after freeze)
        rcba = _deep_unfreeze(self.required_checks_by_archetype)
        if not isinstance(rcba, dict):
            raise ValueError("required_checks_by_archetype must be a dict/object")
        for arch, checks in rcba.items():
            if arch not in required_set:
                raise ValueError(
                    f"required_checks_by_archetype contains unknown archetype {arch!r} "
                    f"(not in required_archetypes)"
                )
            if not isinstance(checks, list):
                raise ValueError(
                    f"required_checks_by_archetype[{arch!r}] must be a list of check names"
                )
            checks_list = list(checks)
            check_dupes = sorted({x for x in checks_list if checks_list.count(x) > 1})
            if check_dupes:
                raise ValueError(
                    f"required_checks_by_archetype[{arch!r}] has duplicate checks: {check_dupes}"
                )
            for chk in checks_list:
                if not chk or not chk.strip():
                    raise ValueError(
                        f"required_checks_by_archetype[{arch!r}] has blank or whitespace-only check name"
                    )

        # required_checks_all: check for duplicates and empty names
        rcall_list = list(self.required_checks_all)
        rcall_dupes = sorted({x for x in rcall_list if rcall_list.count(x) > 1})
        if rcall_dupes:
            raise ValueError(f"required_checks_all has duplicates: {rcall_dupes}")
        for chk in rcall_list:
            if not chk or not chk.strip():
                raise ValueError("required_checks_all has blank or whitespace-only check name")

        return self


class EvalObservation(CoreContractModel):
    case_id: str = Field(min_length=1)
    terminal_status: str = Field(min_length=1)
    cost_inr: float = Field(ge=0.0)
    schema_valid: StrictBool
    check_results: Any = Field(default_factory=dict)  # FrozenJsonDict after construction
    recorded_messages: tuple[Any, ...] = ()

    @field_validator("case_id", "terminal_status", mode="after")
    @classmethod
    def _no_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(f"value must not be whitespace-only, got {v!r}")
        return v  # do NOT strip — reject, don't normalize

    @model_validator(mode="after")
    def _freeze_mutable_fields(self) -> "EvalObservation":
        object.__setattr__(self, "check_results", _deep_freeze(self.check_results))
        object.__setattr__(self, "recorded_messages",
                          tuple(_deep_freeze(m) for m in self.recorded_messages))
        return self

    @model_validator(mode="after")
    def _validate_check_results(self) -> "EvalObservation":
        # Thaw if already frozen by _freeze_mutable_fields (which runs first alphabetically)
        cr = self.check_results
        cr_dict = _json_thaw(cr) if not isinstance(cr, dict) else cr
        if not isinstance(cr_dict, dict):
            raise ValueError(
                f"check_results must be a string-keyed mapping, "
                f"got {type(cr_dict).__name__!r}"
            )
        for k, v in cr_dict.items():
            if not isinstance(k, str) or not k or not k.strip():
                raise ValueError(
                    f"check_results key must be a non-empty, non-whitespace string, got {k!r}"
                )
            # Strict bool check: must be exactly True or False, not truthy/falsy
            if not isinstance(v, bool):
                raise ValueError(
                    f"check_results[{k!r}] must be True or False (strict bool), "
                    f"got {type(v).__name__!r}: {v!r}"
                )
        return self

    @field_serializer("check_results")
    def _serialize_check_results(self, v: Any) -> Any:
        return _deep_unfreeze(v)

    @field_serializer("recorded_messages")
    def _serialize_recorded_messages(self, v: Any) -> Any:
        return [_deep_unfreeze(m) for m in v]


class EvalReport(CoreContractModel):
    dataset_version: str
    total_cases: int = Field(ge=0)
    schema_validity_rate: float = Field(ge=0.0, le=1.0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    injection_resistance_rate: float = Field(ge=0.0, le=1.0)
    average_cost_inr: float = Field(ge=0.0)
    max_cost_inr: float = Field(ge=0.0)
    failures: tuple[str, ...]
    passed: StrictBool

    @model_validator(mode="after")
    def _passed_consistent_with_failures(self) -> "EvalReport":
        expected = len(self.failures) == 0
        if self.passed != expected:
            raise ValueError(
                f"EvalReport.passed={self.passed} inconsistent with "
                f"failures count={len(self.failures)} — "
                f"passed must be True iff failures is empty"
            )
        return self


def load_dataset(path: "str | Path") -> EvalDataset:
    """Load and validate an EvalDataset from a JSON file."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to load dataset from {path}: {exc}") from exc
    try:
        return EvalDataset.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Dataset validation failed for {path}: {exc}") from exc


def load_thresholds(path: "str | Path") -> EvalThresholds:
    """Load and validate EvalThresholds from a YAML file."""
    if _yaml is None:
        raise ImportError("pyyaml is required: pip install pyyaml")
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
        data = _yaml.safe_load(raw)
    except (OSError, Exception) as exc:
        raise ValueError(f"Failed to load thresholds from {path}: {exc}") from exc
    try:
        return EvalThresholds.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Thresholds validation failed for {path}: {exc}") from exc


def evaluate(
    dataset: EvalDataset,
    observations: list[EvalObservation],
    thresholds: EvalThresholds,
) -> EvalReport:
    """Evaluate observations against a dataset and thresholds. Collects ALL failures."""
    failures: list[str] = []

    # 1. Version check
    if dataset.version != thresholds.dataset_version:
        failures.append(
            f"version mismatch: dataset={dataset.version!r} "
            f"thresholds={thresholds.dataset_version!r}"
        )

    # 2. Required archetypes present in dataset
    dataset_archetypes = {c.archetype for c in dataset.cases}
    for arch in thresholds.required_archetypes:
        if arch not in dataset_archetypes:
            failures.append(f"required archetype missing from dataset: {arch!r}")

    # 2b. Extra archetypes not in required_archetypes must fail
    required_archetypes_set = set(thresholds.required_archetypes)
    for arch in sorted(dataset_archetypes):
        if arch not in required_archetypes_set:
            failures.append(
                f"dataset contains unexpected archetype {arch!r} "
                f"not listed in required_archetypes"
            )

    # 3. Observation set exactly matches case set
    obs_by_id: dict[str, EvalObservation] = {}
    for obs in observations:
        if obs.case_id in obs_by_id:
            failures.append(f"duplicate observation for case_id={obs.case_id!r}")
        else:
            obs_by_id[obs.case_id] = obs

    case_ids = {c.id for c in dataset.cases}
    for cid in sorted(case_ids):
        if cid not in obs_by_id:
            failures.append(f"missing observation for case_id={cid!r}")
    for oid in sorted(obs_by_id):  # sorted for deterministic failure messages
        if oid not in case_ids:
            failures.append(f"extra observation with unknown case_id={oid!r}")

    # 3b. Direct terminal-status enforcement — cannot be spoofed via check_results
    for case in dataset.cases:
        obs = obs_by_id.get(case.id)
        if obs is None:
            continue  # already reported as missing
        if obs.terminal_status != case.expected_status:
            failures.append(
                f"case {case.id!r}: terminal_status={obs.terminal_status!r} "
                f"!= expected_status={case.expected_status!r}"
            )

    # 4. Per-case required checks (from dataset)
    for case in dataset.cases:
        obs = obs_by_id.get(case.id)
        if obs is None:
            continue
        # Unfreeze check_results for .get() access
        cr = _deep_unfreeze(obs.check_results)
        for check in case.required_checks:
            if check not in cr:
                failures.append(
                    f"case {case.id!r}: required check {check!r} missing from observation"
                )
            elif not cr[check]:
                failures.append(
                    f"case {case.id!r}: required check {check!r} failed"
                )

    # 4b. Harness-mandated checks from threshold configuration (Issue 1)
    rcba = _deep_unfreeze(thresholds.required_checks_by_archetype)
    for case in dataset.cases:
        obs = obs_by_id.get(case.id)
        if obs is None:
            continue
        cr = _deep_unfreeze(obs.check_results)
        # required_checks_all: every case must pass these
        for check in thresholds.required_checks_all:
            if not cr.get(check, False):
                failures.append(
                    f"case {case.id!r} (archetype={case.archetype!r}): "
                    f"threshold-required check {check!r} failed"
                )
        # required_checks_by_archetype: archetype-specific
        archetype_checks = rcba.get(case.archetype, []) if isinstance(rcba, dict) else []
        for check in archetype_checks:
            if not cr.get(check, False):
                failures.append(
                    f"case {case.id!r} (archetype={case.archetype!r}): "
                    f"threshold-required check {check!r} failed"
                )

    # 5. Compute metrics
    valid_obs = [obs_by_id[c.id] for c in dataset.cases if c.id in obs_by_id]

    if valid_obs:
        schema_valid_count = sum(1 for o in valid_obs if o.schema_valid)
        schema_validity_rate = schema_valid_count / len(valid_obs)
    else:
        schema_validity_rate = 0.0
        failures.append("no valid observations — schema_validity_rate cannot be computed")

    # Pass rate — use thresholds.pass_rate_archetypes exclusively
    _pass_rate_archetypes = set(thresholds.pass_rate_archetypes)
    eligible = [
        obs_by_id[c.id]
        for c in dataset.cases
        if c.id in obs_by_id and c.archetype in _pass_rate_archetypes
    ]
    if not eligible:
        failures.append(
            "no pass-rate-eligible cases found — cannot compute pass_rate"
        )
        pass_rate = 0.0
    else:
        passed_count = sum(1 for o in eligible if o.terminal_status == "pass")
        pass_rate = passed_count / len(eligible)

    # Injection resistance — uses injection_archetypes from thresholds (Issue 1)
    _inj_archetypes = set(thresholds.injection_archetypes)
    inj_cases = [
        obs_by_id[c.id]
        for c in dataset.cases
        if c.id in obs_by_id and c.archetype in _inj_archetypes
    ]
    if inj_cases:
        inj_resisted = sum(
            1 for o in inj_cases
            if _deep_unfreeze(o.check_results).get("injection_resisted", False)
        )
        injection_resistance_rate = inj_resisted / len(inj_cases)
    elif thresholds.minimum_injection_resistance > 0:
        # No injection-archetype cases found — cannot compute rate
        injection_resistance_rate = 0.0
        failures.append(
            "no injection-archetype cases found — "
            "injection_resistance_rate cannot be computed; "
            "add a case with archetype in injection_archetypes"
        )
    else:
        injection_resistance_rate = 1.0  # vacuously passing when threshold is 0

    costs = [o.cost_inr for o in valid_obs]
    average_cost_inr = sum(costs) / len(costs) if costs else 0.0
    max_cost_inr = max(costs) if costs else 0.0

    # 6. Threshold checks
    if schema_validity_rate < thresholds.minimum_schema_validity:
        failures.append(
            f"schema_validity_rate={schema_validity_rate:.4f} < "
            f"minimum={thresholds.minimum_schema_validity}"
        )
    if eligible and pass_rate < thresholds.minimum_pass_rate:
        failures.append(
            f"pass_rate={pass_rate:.4f} < minimum={thresholds.minimum_pass_rate} "
            f"({sum(1 for o in eligible if o.terminal_status == 'pass')}/{len(eligible)} "
            f"eligible cases passed)"
        )
    if injection_resistance_rate < thresholds.minimum_injection_resistance:
        failures.append(
            f"injection_resistance_rate={injection_resistance_rate:.4f} < "
            f"minimum={thresholds.minimum_injection_resistance}"
        )
    # STRICT less-than for per-run cost
    for o in valid_obs:
        if o.cost_inr >= thresholds.max_cost_per_run_inr_exclusive:
            failures.append(
                f"case {o.case_id!r}: cost_inr={o.cost_inr} >= "
                f"max_exclusive={thresholds.max_cost_per_run_inr_exclusive}"
            )
    # INCLUSIVE less-than-or-equal for average
    if average_cost_inr > thresholds.max_average_cost_inr_inclusive:
        failures.append(
            f"average_cost_inr={average_cost_inr:.4f} > "
            f"max_inclusive={thresholds.max_average_cost_inr_inclusive}"
        )

    return EvalReport(
        dataset_version=dataset.version,
        total_cases=len(dataset.cases),
        schema_validity_rate=schema_validity_rate,
        pass_rate=pass_rate,
        injection_resistance_rate=injection_resistance_rate,
        average_cost_inr=average_cost_inr,
        max_cost_inr=max_cost_inr,
        failures=tuple(failures),
        passed=len(failures) == 0,
    )


def assert_eval_report(report: EvalReport) -> None:
    """Raise AssertionError if the report has any failures.

    Checks failures directly — does not rely solely on report.passed.
    """
    if report.failures:
        raise AssertionError(
            f"Eval report failed with {len(report.failures)} issue(s):\n"
            + "\n".join(f"  - {f}" for f in report.failures)
        )
    if not report.passed:
        raise AssertionError(
            "EvalReport.passed=False with empty failures — data integrity error"
        )
