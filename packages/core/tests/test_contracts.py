"""Contract tests for the hardened core models (offline, no network/keys).

Covers: CoreContractModel (extra=forbid, frozen, copy revalidation), Usage (non-negative /
non-finite / currency), LLMResponse (payload exclusivity, structured-output schema enforcement,
JSON serialization), ToolCall.args (JSON-only, deep immutability, pickle/deepcopy), and
Transcript / TimestampSegment (ordering, duration bound, non-finite).
"""

from __future__ import annotations

import json
import pickle

import pytest
from pydantic import ConfigDict, ValidationError, create_model

from core import CoreContractModel, LLMResponse, TimestampSegment, ToolCall, Transcript, Usage

Good = create_model("Good", __base__=CoreContractModel, items=(tuple[str, ...], ()))
BadList = create_model("BadList", __base__=CoreContractModel, items=(list, ...))
PlainFrozen = create_model("PlainFrozen", __config__=ConfigDict(frozen=True), x=(int, 0))
INF = float("inf")
NAN = float("nan")


# --- CoreContractModel -----------------------------------------------------------------------

def test_extra_forbid():
    with pytest.raises(ValidationError):
        Usage(unknown_field=1)


def test_frozen_blocks_mutation():
    with pytest.raises(ValidationError):
        Usage().cost_native = -1.0


def test_model_copy_update_revalidates():
    with pytest.raises(ValidationError):
        Usage().model_copy(update={"cost_native": -5})
    with pytest.raises(ValidationError):
        Usage().model_copy(update={"typo": 1})  # extra=forbid in copy too
    assert Usage(prompt_tokens=1).model_copy(update={"prompt_tokens": 2}).prompt_tokens == 2


def test_validated_copy():
    assert Usage(prompt_tokens=1).validated_copy(prompt_tokens=3).prompt_tokens == 3
    with pytest.raises(ValidationError):
        Usage().validated_copy(cost_native=-1)


# --- Usage -----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kw",
    [
        {"cost_native": -0.01, "currency": "USD"},
        {"prompt_tokens": -1},
        {"audio_seconds": -1.0},
        {"cost_native": INF, "currency": "USD"},
        {"cost_native": NAN, "currency": "USD"},
    ],
)
def test_usage_rejects_invalid(kw):
    with pytest.raises(ValidationError):
        Usage(**kw)


def test_currency_fail_closed_and_normalize():
    with pytest.raises(ValidationError):
        Usage(cost_native=5.0)  # missing currency on billable usage
    with pytest.raises(ValidationError):
        Usage(cost_native=5.0, currency="   ")  # whitespace currency
    assert Usage(cost_native=5.0, currency=" usd ").currency == "USD"
    assert Usage().currency is None  # free/synthetic -> no currency required


# --- LLMResponse -----------------------------------------------------------------------------

def test_payload_exclusivity():
    with pytest.raises(ValidationError):
        LLMResponse()
    with pytest.raises(ValidationError):
        LLMResponse(text="a", structured=Good(items=("z",)))
    assert LLMResponse(text="hi").text == "hi"


def test_structured_output_schema_enforcement():
    with pytest.raises(ValidationError):
        LLMResponse.structured_from(PlainFrozen, {"x": 1})  # not a CoreContractModel
    with pytest.raises(ValidationError):
        LLMResponse.structured_from(BadList, {"items": ["a"]})  # mutable list field
    with pytest.raises(ValidationError):
        LLMResponse.structured_from(Good, {"items": ["a"], "unexpected": 1})  # extra=forbid mismatch
    r = LLMResponse.structured_from(Good, {"items": ["a", "b"]})
    assert r.structured.items == ("a", "b")


def test_structured_immutable():
    r = LLMResponse.structured_from(Good, {"items": ["a", "b"]})
    with pytest.raises(AttributeError):
        r.structured.items.append("c")  # tuple
    with pytest.raises(ValidationError):
        r.structured.items = ("c",)  # frozen


def test_structured_json_serialization():
    r = LLMResponse.structured_from(Good, {"items": ["a", "b"]})
    assert r.model_dump(mode="json")["structured"] == {"items": ["a", "b"]}
    json.dumps(r.model_dump(mode="json"))  # JSON-serializable


# --- ToolCall.args ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "args",
    [{"a": {1, 2}}, {"a": Usage()}, {"a": INF}, {"a": NAN}, {1: "x"}],
)
def test_toolcall_args_json_only(args):
    with pytest.raises(ValidationError):
        ToolCall(name="f", args=args)


def test_toolcall_args_immutable_serializable_checkpointable():
    tc = ToolCall(name="f", args={"a": [1, 2], "b": {"c": 3}})
    with pytest.raises(TypeError):
        tc.args["a"] = 9
    with pytest.raises(TypeError):
        tc.args["b"]["c"] = 9
    dumped = tc.model_dump()
    assert dumped["args"] == {"a": [1, 2], "b": {"c": 3}}
    json.dumps(dumped)  # serializable
    tc2 = pickle.loads(pickle.dumps(tc))  # checkpoint/pickle round-trip
    assert tc2.model_dump() == dumped
    with pytest.raises(TypeError):
        tc2.args["a"] = 9
    tc3 = tc.model_copy(deep=True)  # deepcopy compatibility
    assert tc3.model_dump() == dumped


# --- Transcript / TimestampSegment -----------------------------------------------------------

def test_transcript_validation():
    with pytest.raises(ValidationError):
        Transcript(text="x", duration_s=INF)
    with pytest.raises(ValidationError):
        Transcript(text="x", confidence=1.5)
    s1 = TimestampSegment(start_s=0.0, end_s=1.0, text="a")
    s2 = TimestampSegment(start_s=2.0, end_s=3.0, text="b")
    Transcript(text="x", segments=[s1, s2], duration_s=3.0)  # OK
    with pytest.raises(ValidationError):
        Transcript(text="x", segments=[s2, s1])  # out of order
    with pytest.raises(ValidationError):
        Transcript(text="x", segments=[s2], duration_s=2.5)  # beyond duration
    with pytest.raises(ValidationError):
        TimestampSegment(start_s=5.0, end_s=1.0, text="a")  # start > end
    assert isinstance(Transcript(text="x", segments=[s1]).segments, tuple)


def test_usage_json_round_trip():
    u = Usage(prompt_tokens=3, completion_tokens=5, cost_native=1.25, currency="usd")
    payload = json.loads(u.model_dump_json())
    assert payload["currency"] == "USD" and payload["cost_native"] == 1.25
