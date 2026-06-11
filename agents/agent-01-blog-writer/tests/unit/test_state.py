"""Unit tests — BlogState shape and reducer semantics (DESIGN §2).

Verifies:
- BlogState is a TypedDict
- hard_fail_flags uses operator.add (accumulation, not last-write-wins)
- cost_usage uses operator.add (accumulation)
- All expected field names are present in the annotation
- cost_gate_ok field is present for routing
"""

from __future__ import annotations

import operator
from typing import Annotated, get_type_hints

import pytest

from agent.schemas import StageCost
from agent.state import BlogState


# ---------------------------------------------------------------------------
# 1. TypedDict identity
# ---------------------------------------------------------------------------

def test_blog_state_is_typeddict():
    # TypedDicts expose __annotations__ and __total__
    assert hasattr(BlogState, "__annotations__")
    assert hasattr(BlogState, "__total__")
    # total=False means all keys are optional
    assert BlogState.__total__ is False


# ---------------------------------------------------------------------------
# 2. Expected field names present
# ---------------------------------------------------------------------------

_EXPECTED_FIELDS = {
    "raw_input",
    "input_type",
    "writing_prefs",
    "normalized_content",
    "extracted_ideas",
    "blog_plan",
    "draft",
    "quality",
    "revision_count",
    "hard_fail_flags",
    "cost_usage",
    "cost_gate_ok",
    "error_state",
    "status",
    "final_output",
}


def test_blog_state_has_expected_fields():
    annotations = BlogState.__annotations__
    missing = _EXPECTED_FIELDS - set(annotations)
    assert missing == set(), f"Missing fields: {missing}"


# ---------------------------------------------------------------------------
# 3. operator.add reducer on hard_fail_flags
# ---------------------------------------------------------------------------

def test_hard_fail_flags_has_add_reducer():
    """Confirm the annotation uses Annotated[list[str], operator.add]."""
    # get_type_hints() evaluates stringified annotations (from __future__ import annotations)
    hints = get_type_hints(BlogState, include_extras=True)
    annotation = hints["hard_fail_flags"]
    metadata = getattr(annotation, "__metadata__", ())
    assert operator.add in metadata, (
        "hard_fail_flags must use Annotated[list[str], operator.add] so flags "
        "accumulate across review cycles — last-write-wins would silently drop earlier flags"
    )


def test_hard_fail_flags_accumulation_semantics():
    """Simulate what LangGraph does: reducer(existing, update) = existing + update."""
    # LangGraph calls operator.add(existing_list, update_list) for accumulator fields.
    existing = ["injection_followed"]
    update = ["factual_error"]
    result = operator.add(existing, update)
    assert result == ["injection_followed", "factual_error"]
    # Critically: earlier flags are NOT lost
    assert "injection_followed" in result
    assert "factual_error" in result


def test_hard_fail_flags_accumulation_is_not_last_write_wins():
    """Demonstrate why last-write-wins would be wrong."""
    existing = ["injection_followed"]
    update = ["factual_error"]
    # last-write-wins would give only the update:
    last_write_wins = update
    assert last_write_wins != ["injection_followed", "factual_error"]
    # operator.add preserves all flags:
    assert operator.add(existing, update) == ["injection_followed", "factual_error"]


# ---------------------------------------------------------------------------
# 4. operator.add reducer on cost_usage
# ---------------------------------------------------------------------------

def test_cost_usage_has_add_reducer():
    """Confirm cost_usage uses Annotated[list[StageCost], operator.add]."""
    hints = get_type_hints(BlogState, include_extras=True)
    annotation = hints["cost_usage"]
    metadata = getattr(annotation, "__metadata__", ())
    assert operator.add in metadata, (
        "cost_usage must use operator.add so each node's StageCost is appended, "
        "not overwritten"
    )


def test_cost_usage_accumulation_semantics():
    """Simulate LangGraph accumulation: each node appends one StageCost."""
    sc1 = StageCost(stage="normalize", cost_inr=0.5, tier="cheap")
    sc2 = StageCost(stage="draft", cost_inr=10.0, tier="strong")
    sc3 = StageCost(stage="review", cost_inr=5.0, tier="strong")

    # Simulate graph merging: normalize → draft → review
    accumulated = operator.add([], [sc1])      # after normalize
    accumulated = operator.add(accumulated, [sc2])  # after draft
    accumulated = operator.add(accumulated, [sc3])  # after review

    assert len(accumulated) == 3
    total = sum(sc.cost_inr for sc in accumulated)
    assert abs(total - 15.5) < 1e-9


# ---------------------------------------------------------------------------
# 5. cost_gate_ok field is bool-annotated
# ---------------------------------------------------------------------------

def test_cost_gate_ok_field_exists():
    assert "cost_gate_ok" in BlogState.__annotations__


# ---------------------------------------------------------------------------
# 6. Annotated unwrapping — verify the inner type of accumulators
# ---------------------------------------------------------------------------

def test_hard_fail_flags_inner_type():
    """The inner type of the Annotated annotation should be list[str]."""
    import typing
    hints = get_type_hints(BlogState, include_extras=True)
    annotation = hints["hard_fail_flags"]
    args = typing.get_args(annotation)
    # args[0] is the base type, args[1..] are metadata
    assert args, "hard_fail_flags must be Annotated[list[str], operator.add]"
    base_type = args[0]
    # list[str] — check it's a list-like parameterized generic
    origin = typing.get_origin(base_type)
    assert origin is list


def test_cost_usage_inner_type():
    """The inner type of the Annotated annotation should be list[StageCost]."""
    import typing
    hints = get_type_hints(BlogState, include_extras=True)
    annotation = hints["cost_usage"]
    args = typing.get_args(annotation)
    assert args, "cost_usage must be Annotated[list[StageCost], operator.add]"
    base_type = args[0]
    origin = typing.get_origin(base_type)
    assert origin is list
