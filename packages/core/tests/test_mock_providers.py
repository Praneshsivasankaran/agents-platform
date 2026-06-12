"""Tests for the offline mock providers and the config-driven factory (keyless / no network).

Covers:
- MockLLMProvider: text output, unconstrained structured schemas, constrained schemas (ge/le/
  min_length/tuple min_length, mixed-constraint).
- MockTranscriptionProvider: Transcript contract.
- InMemoryObjectStorage, EnvSecretStore: basic CRUD.
- StdoutTelemetry (provenance-based security model): registered-label enforcement; separate
  metric-name registry (strict subset of event labels); injected per-agent labels, dimensions,
  attr-keys, and metric-names; wholesale redaction of nested structures (no recursion);
  all log/span numeric attributes always redacted; metric() redacts value when name is
  unregistered; record_usage() requires real Usage instance + model_validate revalidation
  (catches model_construct() bypass); strict JSON (no NaN); sensitive-key and reserved-field
  protection; attrs nesting; label/control-char sanitization; deterministic trace-id/span-id.
- Factory: mock path wired; cloud paths raise NotImplementedError; telemetry extra_labels +
  dimensions + attr_keys + extra_metric_names all wired from config.
"""

from __future__ import annotations

import io
import json

import pytest
from pydantic import Field, create_model

from core import CoreContractModel, LLMResponse, Transcript
from core.interfaces.llm import LLMProvider
from core.factory import (
    get_llm_provider,
    get_object_storage,
    get_secret_store,
    get_telemetry,
    get_transcription_provider,
)
from core.providers.mock import (
    EnvSecretStore,
    InMemoryObjectStorage,
    MockLLMProvider,
    MockTranscriptionProvider,
    StdoutTelemetry,
)


# ---------------------------------------------------------------------------
# MockLLMProvider — text
# ---------------------------------------------------------------------------


def test_mock_llm_text():
    r = MockLLMProvider().respond([{"role": "user", "content": "hello"}], tier="cheap")
    assert isinstance(r, LLMResponse)
    assert r.text and r.usage.synthetic and r.usage.cost_native == 0.0


# ---------------------------------------------------------------------------
# MockLLMProvider — unconstrained structured output
# ---------------------------------------------------------------------------


def test_mock_llm_structured_schema_valid():
    schema = create_model("S", __base__=CoreContractModel, title=(str, ...), tags=(tuple[str, ...], ()))
    r = MockLLMProvider().respond([{"role": "user", "content": "x"}], tier="strong", response_schema=schema)
    assert isinstance(r.structured, schema)
    # Ninth repair: _placeholder for str now returns "x" (min 1 char) instead of ""
    # so that unconstrained str fields never produce empty strings that fail non-blank validators.
    assert r.model_dump(mode="json")["structured"] == {"title": "x", "tags": []}


# ---------------------------------------------------------------------------
# MockLLMProvider — constraint-aware structured output
# ---------------------------------------------------------------------------


def test_mock_llm_constrained_int_ge():
    """int field with ge=1 must receive 1, not 0 (which would fail validation)."""
    schema = create_model(
        "WithGeInt", __base__=CoreContractModel,
        count=(int, Field(ge=1)),
    )
    r = MockLLMProvider().respond([{"role": "user", "content": "x"}], tier="cheap", response_schema=schema)
    assert isinstance(r.structured, schema)
    assert r.structured.count >= 1


def test_mock_llm_constrained_int_ge_le():
    """int field with ge=3, le=5 must fall in [3, 5]."""
    schema = create_model(
        "Bounded", __base__=CoreContractModel,
        score=(int, Field(ge=3, le=5)),
    )
    r = MockLLMProvider().respond([{"role": "user", "content": "x"}], tier="cheap", response_schema=schema)
    assert 3 <= r.structured.score <= 5


def test_mock_llm_constrained_float_ge():
    """float field with ge=0.5 must receive >= 0.5."""
    schema = create_model(
        "Prob", __base__=CoreContractModel,
        confidence=(float, Field(ge=0.5, le=1.0)),
    )
    r = MockLLMProvider().respond([{"role": "user", "content": "x"}], tier="cheap", response_schema=schema)
    assert 0.5 <= r.structured.confidence <= 1.0


def test_mock_llm_constrained_string_min_length():
    """str field with min_length=3 must receive a string of length >= 3."""
    schema = create_model(
        "Named", __base__=CoreContractModel,
        label=(str, Field(min_length=3)),
    )
    r = MockLLMProvider().respond([{"role": "user", "content": "x"}], tier="cheap", response_schema=schema)
    assert len(r.structured.label) >= 3


def test_mock_llm_constrained_tuple_min_length():
    """tuple[str, ...] field with min_length=2 must receive at least 2 elements."""
    schema = create_model(
        "Tagged", __base__=CoreContractModel,
        tags=(tuple[str, ...], Field(min_length=2)),
    )
    r = MockLLMProvider().respond([{"role": "user", "content": "x"}], tier="cheap", response_schema=schema)
    assert len(r.structured.tags) >= 2


def test_mock_llm_constrained_schema_passes_validation():
    """A schema mixing several constraints must pass structured_from validation without error."""
    schema = create_model(
        "Mixed", __base__=CoreContractModel,
        count=(int, Field(ge=1)),
        ratio=(float, Field(ge=0.0, le=1.0)),
        name=(str, Field(min_length=1)),
        items=(tuple[str, ...], Field(min_length=1)),
    )
    r = MockLLMProvider().respond([{"role": "user", "content": "x"}], tier="strong", response_schema=schema)
    assert isinstance(r.structured, schema)


# ---------------------------------------------------------------------------
# MockTranscriptionProvider
# ---------------------------------------------------------------------------


def test_mock_transcription():
    t = MockTranscriptionProvider().transcribe("audio://x", timestamps=True)
    assert isinstance(t, Transcript)
    assert t.text and t.provider == "mock" and t.usage.synthetic
    assert t.segments and t.segments[0].end_s <= t.duration_s


# ---------------------------------------------------------------------------
# InMemoryObjectStorage
# ---------------------------------------------------------------------------


def test_in_memory_object_storage():
    s = InMemoryObjectStorage()
    assert s.put("k", b"v") == "k"
    assert s.get("k") == b"v"
    s.delete("k")
    with pytest.raises(KeyError):
        s.get("k")


# ---------------------------------------------------------------------------
# EnvSecretStore
# ---------------------------------------------------------------------------


def test_env_secret_store(monkeypatch):
    s = EnvSecretStore()
    monkeypatch.setenv("MY_SECRET", "abc")
    assert s.get("MY_SECRET") == "abc"
    assert s.get("DEFINITELY_MISSING_XYZ") is None


# ===========================================================================
# StdoutTelemetry
#
# The telemetry security model is provenance-based (see telemetry.py docstring):
#   - msg/span-name must be a REGISTERED event label (platform set + injected extra_labels).
#   - metric-name must be a REGISTERED metric name (_PLATFORM_METRIC_NAMES + extra_metric_names);
#     metric names are a strict subset of event labels — "node.complete" is NOT a metric name.
#   - attribute string values pass only under a registered DIMENSION enum (finite frozenset);
#     agent-specific dimensions (node, stage) are INJECTED, not hardcoded in shared core.
#   - nested structures (dict/list/model/object) are redacted WHOLESALE — never walked.
#   - ALL int/float log/span attribute values are redacted; numbers are not a log channel.
#     Real measurements go through metric() (registered name + finite value) or record_usage()
#     (validated Usage instance, revalidated via model_validate(model_dump())).
#   - record_usage() requires an actual Usage instance; model_construct() bypasses are caught.
#
# These constants emulate what an agent (or the factory, from config) injects.  Shared core
# ships NEITHER of them — that is the decoupling the platform requires.
# ===========================================================================

AGENT_LABELS = frozenset({
    "intake.started", "intake.complete",
    "normalize.complete", "extract.complete", "plan.complete",
    "draft.started", "draft.complete",
    "review.complete", "finalize.complete",
})

AGENT_DIMENSIONS = {
    "node": frozenset({
        "intake", "normalize", "extract", "plan", "draft", "review", "finalize", "transcribe",
    }),
    "stage": frozenset({"intake", "plan", "draft", "review", "finalize"}),
}


def _tel(buf, **kw):
    """StdoutTelemetry preloaded with the per-agent label + dimension injections.

    Mirrors how a real agent constructs telemetry: shared-core platform taxonomy PLUS the
    agent's own event codes and dimension enums.
    """
    kw.setdefault("extra_labels", AGENT_LABELS)
    kw.setdefault("dimensions", AGENT_DIMENSIONS)
    return StdoutTelemetry(stream=buf, **kw)


# ---------------------------------------------------------------------------
# StdoutTelemetry — basic emission
# ---------------------------------------------------------------------------


def test_stdout_telemetry_emits():
    buf = io.StringIO()
    tel = _tel(buf)
    with tel.span("node.started", node="intake"):
        tel.log("node.complete", passed=True)
        tel.metric("llm.cost_inr", 0.0)
        tel.record_usage(__import__("core").Usage(prompt_tokens=1, synthetic=True))
    events = [json.loads(line)["event"] for line in buf.getvalue().splitlines()]
    assert {"span_start", "span_end", "log", "metric", "usage"} <= set(events)


# ---------------------------------------------------------------------------
# StdoutTelemetry — sensitive-key redaction
# ---------------------------------------------------------------------------


def test_telemetry_redacts_sensitive_keys():
    """Sensitive field values must be replaced with '[REDACTED]'; a registered bool flag passes."""
    buf = io.StringIO()
    tel = _tel(buf, _trace_id="test-trace")
    tel.log("node.complete", text="USER CONTENT", prompt="system prompt", passed=True)
    record = json.loads(buf.getvalue().strip())
    attrs = record.get("attrs", {})
    assert attrs.get("text") == "[REDACTED]", "text must be redacted"
    assert attrs.get("prompt") == "[REDACTED]", "prompt must be redacted"
    assert attrs.get("passed") is True, "registered bool flag must pass through"


@pytest.mark.parametrize("sensitive_key", [
    "text", "content", "prompt", "transcript", "draft", "raw_input",
    "input", "output", "secret", "api_key", "token", "password", "authorization",
    "access_token", "client_secret", "credentials", "headers", "cookies",
])
def test_telemetry_redacts_every_sensitive_key(sensitive_key):
    """Every documented sensitive key must be redacted."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("node.complete", **{sensitive_key: "should-be-hidden"})
    record = json.loads(buf.getvalue().strip())
    attrs = record.get("attrs", {})
    assert attrs.get(sensitive_key) == "[REDACTED]", (
        f"Sensitive key '{sensitive_key}' must be redacted in log output"
    )


def test_telemetry_redacts_case_insensitive_keys():
    """Sensitive key matching must be case-insensitive (Authorization, AUTHORIZATION)."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("provider.call", Authorization="Bearer SECRET_TOKEN", AUTHORIZATION="also-secret")
    record = json.loads(buf.getvalue().strip())
    attrs = record.get("attrs", {})
    assert attrs.get("Authorization") == "[REDACTED]", "Capital-A Authorization must be redacted"
    assert attrs.get("AUTHORIZATION") == "[REDACTED]", "ALL-CAPS AUTHORIZATION must be redacted"


# ---------------------------------------------------------------------------
# StdoutTelemetry — nested structures redacted WHOLESALE (no recursion)
# ---------------------------------------------------------------------------


def test_telemetry_nested_mapping_redacted_wholesale():
    """A nested Mapping attr is redacted wholesale — the channel never walks user structures.

    Codex Round 7 finding: walking nested structures to 'salvage' approved keys re-opens the
    PII channel — ``metadata={"count": <phone_number>}`` passed because ``count`` was an
    approved numeric key at any depth.  The provenance model treats any nested structure as
    opaque user data and replaces the WHOLE value with ``"[REDACTED]"`` — there is no nested
    approved key, because nesting is never entered.
    """
    # 'metadata' is registered here to isolate VALUE behavior; an unregistered key would
    # collapse to [redacted_key] (see test_telemetry_identifier_shaped_user_key_redacted).
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, attr_keys=frozenset({"metadata"}))
    tel.log("node.complete", metadata={"text": "NESTED SECRET", "count": 5551234567})
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert attrs.get("metadata") == "[REDACTED]", (
        "A nested mapping must be redacted wholesale, not walked"
    )
    assert "NESTED SECRET" not in output
    assert "5551234567" not in output, "Nested numeric PII must not leak"


def test_telemetry_nested_list_redacted_wholesale():
    """A nested list attr is redacted wholesale, including any numbers/strings inside it."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, attr_keys=frozenset({"items"}))
    tel.log("node.complete", items=[{"token": "SECRET1"}, {"count": 987654321}])
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert attrs.get("items") == "[REDACTED]", "A nested list must be redacted wholesale"
    assert "SECRET1" not in output
    assert "987654321" not in output, "Numeric PII nested in a list must not leak"


# ---------------------------------------------------------------------------
# StdoutTelemetry — reserved-field protection
# ---------------------------------------------------------------------------


def test_telemetry_reserved_fields_not_overwritten():
    """Caller-supplied kwargs matching reserved keys must be silently dropped."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, _trace_id="real-trace-id")
    tel.log("node.complete", event="hacked", trace_id="attacker", span_id="evil", level="CRITICAL")
    record = json.loads(buf.getvalue().strip())
    assert record["event"] == "log", "event must be 'log', not the caller-supplied value"
    assert record["trace_id"] == "real-trace-id", "trace_id must not be overwritten by caller"
    assert record.get("span_id") is None, "span_id must not be injected via log() kwargs"


def test_telemetry_reserved_field_protection_case_insensitive():
    """Reserved key protection is case-insensitive (Event, TRACE_ID must also be stripped)."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, _trace_id="real-id")
    tel.log("node.complete", Event="hijack", TRACE_ID="override")
    record = json.loads(buf.getvalue().strip())
    assert record.get("Event") is None
    assert record.get("TRACE_ID") is None
    assert record["event"] == "log"
    assert record["trace_id"] == "real-id"


def test_telemetry_user_attrs_nested_under_attrs_key():
    """User-supplied kwargs must be nested under 'attrs', not at the top level."""
    buf = io.StringIO()
    tel = _tel(buf)
    tel.log("node.complete", node="intake", stage="plan")
    record = json.loads(buf.getvalue().strip())
    assert "attrs" in record, "User kwargs must be nested under 'attrs'"
    assert record["attrs"].get("node") == "intake"
    assert record["attrs"].get("stage") == "plan"
    assert "node" not in record, "User kwarg 'node' must not appear at top level"
    assert "stage" not in record, "User kwarg 'stage' must not appear at top level"


def test_telemetry_span_attrs_nested_and_redacted():
    """Span attrs are nested under 'attrs'; sensitive span attrs are redacted."""
    buf = io.StringIO()
    tel = _tel(buf)
    with tel.span("node.started", stage="draft", content="SECRET"):
        pass
    lines = [json.loads(line) for line in buf.getvalue().splitlines()]
    span_start = next(r for r in lines if r["event"] == "span_start")
    assert "attrs" in span_start
    assert span_start["attrs"].get("stage") == "draft"
    assert span_start["attrs"].get("content") == "[REDACTED]"
    assert "stage" not in span_start
    assert "content" not in span_start


# ---------------------------------------------------------------------------
# StdoutTelemetry — label / control-char sanitization
# ---------------------------------------------------------------------------


def test_telemetry_unregistered_long_msg_redacted_and_bounded():
    """An over-long unregistered msg becomes '[redacted_label]' (bounded length)."""
    from core.providers.mock.telemetry import _MAX_LABEL_LEN
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("x" * (_MAX_LABEL_LEN + 300))
    record = json.loads(buf.getvalue().strip())
    assert record["msg"] == "[redacted_label]"
    assert len(record["msg"]) <= _MAX_LABEL_LEN


def test_telemetry_msg_control_chars_stripped():
    """Newlines/carriage returns must never appear in an emitted label (log-injection guard)."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("line1\nline2\r")
    record = json.loads(buf.getvalue().strip())
    assert "\n" not in record["msg"]
    assert "\r" not in record["msg"]


def test_telemetry_metric_name_sanitized():
    """Metric name must be truncated and control-char-stripped before the registry check."""
    from core.providers.mock.telemetry import _MAX_LABEL_LEN
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.metric("llm.cost\n" + "x" * 300, 1.0)
    record = json.loads(buf.getvalue().strip())
    assert "\n" not in record["name"]
    assert len(record["name"]) <= _MAX_LABEL_LEN


# ---------------------------------------------------------------------------
# StdoutTelemetry — deterministic test injection
# ---------------------------------------------------------------------------


def test_telemetry_deterministic_trace_id():
    """Injected _trace_id appears in every emitted record."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, _trace_id="deterministic-id-123")
    tel.log("node.complete")
    tel.metric("llm.cost_inr", 1.0)
    for line in buf.getvalue().splitlines():
        assert json.loads(line)["trace_id"] == "deterministic-id-123"


def test_telemetry_deterministic_span_id():
    """Injected _span_id_factory produces deterministic span ids."""
    buf = io.StringIO()
    counter = {"n": 0}

    def factory():
        counter["n"] += 1
        return f"span-{counter['n']:04d}"

    tel = StdoutTelemetry(stream=buf, _span_id_factory=factory)
    with tel.span("node.started"):
        pass
    lines = [json.loads(line) for line in buf.getvalue().splitlines()]
    span_start = next(r for r in lines if r["event"] == "span_start")
    span_end = next(r for r in lines if r["event"] == "span_end")
    assert span_start["span_id"] == "span-0001"
    assert span_end["span_id"] == "span-0001"


# ---------------------------------------------------------------------------
# StdoutTelemetry — Pydantic / object payloads redacted wholesale
# ---------------------------------------------------------------------------


def test_telemetry_pydantic_model_payload_redacted():
    """A Pydantic model attr value is redacted wholesale — never dumped or stringified."""
    Schema = create_model(
        "PayloadSchema",
        __base__=CoreContractModel,
        text=(str, "MODEL SECRET"),
        safe=(str, "SAFE VALUE"),
        score=(int, 42),
    )
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, attr_keys=frozenset({"payload"}))
    tel.log("node.complete", payload=Schema())

    output = buf.getvalue()
    assert json.loads(output.strip()).get("attrs", {}).get("payload") == "[REDACTED]", (
        "A Pydantic model attr must be redacted wholesale (structures are opaque)"
    )
    assert "MODEL SECRET" not in output
    assert "SAFE VALUE" not in output


def test_telemetry_pydantic_model_nested_in_list_redacted():
    """Pydantic models nested inside a list attr are redacted with the whole list."""
    Schema = create_model(
        "Item", __base__=CoreContractModel,
        token=(str, "LIST_SECRET"),
        label=(str, "ok"),
    )
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, attr_keys=frozenset({"items"}))
    tel.log("node.complete", items=[Schema(), Schema()])

    output = buf.getvalue()
    assert json.loads(output.strip()).get("attrs", {}).get("items") == "[REDACTED]"
    assert "LIST_SECRET" not in output


def test_telemetry_arbitrary_object_redacted_not_stringified():
    """Arbitrary objects are '[REDACTED]', never stringified via str()/repr()."""
    class LeakingObject:
        def __str__(self) -> str:
            return "SECRET_IN_STR_REPR"
        def __repr__(self) -> str:
            return "LeakingObject(SECRET_IN_REPR)"

    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, attr_keys=frozenset({"bad_payload"}))
    tel.log("node.complete", bad_payload=LeakingObject())

    output = buf.getvalue()
    assert json.loads(output.strip()).get("attrs", {}).get("bad_payload") == "[REDACTED]"
    assert "SECRET_IN_STR_REPR" not in output
    assert "SECRET_IN_REPR" not in output


# ---------------------------------------------------------------------------
# StdoutTelemetry — label registry (membership, not regex)
# ---------------------------------------------------------------------------


def test_telemetry_raw_uppercase_msg_not_emitted():
    """An unregistered msg (e.g. user content) becomes '[redacted_label]', never verbatim."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("RAW USER SECRET")
    output = buf.getvalue()
    record = json.loads(output.strip())
    assert record["msg"] == "[redacted_label]"
    assert "RAW USER SECRET" not in output


def test_telemetry_registered_platform_label_passes():
    """A registered platform label is emitted as-is."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("node.started")
    record = json.loads(buf.getvalue().strip())
    assert record["msg"] == "node.started"


def test_telemetry_bare_word_and_phrase_labels_blocked():
    """Bare words ('secret') and phrases must be blocked — membership, not regex, is authority."""
    for label in ("secret", "my private client strategy"):
        buf = io.StringIO()
        tel = StdoutTelemetry(stream=buf)
        tel.log(label)
        output = buf.getvalue()
        record = json.loads(output.strip())
        assert record["msg"] == "[redacted_label]", f"{label!r} must be blocked (not registered)"
        assert label not in output


def test_telemetry_blog_domain_string_attrs_redacted_by_default():
    """Domain fields (title, main_idea, full_draft) are unregistered keys → '[redacted_key]'.

    These keys are neither dimensions nor registered attribute keys, so both the KEY and the
    VALUE are suppressed: the key collapses to ``[redacted_key]`` and the value to ``[REDACTED]``.
    The platform never needs to enumerate every sensitive field name.
    """
    buf = io.StringIO()
    tel = _tel(buf)
    tel.log("draft.complete",
            title="Cats and Their Owners: A Deep Dive",
            main_idea="The bond between humans and cats is reciprocal",
            full_draft="Once upon a time there was a cat...")
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert "title" not in attrs and "main_idea" not in attrs and "full_draft" not in attrs, (
        "Unregistered domain keys must not appear verbatim"
    )
    assert attrs.get("[redacted_key]") == "[REDACTED]"
    assert "Deep Dive" not in output
    assert "reciprocal" not in output
    assert "Once upon a time" not in output


# ---------------------------------------------------------------------------
# StdoutTelemetry — approved finite numerics / bools
# ---------------------------------------------------------------------------


def test_telemetry_log_numerics_always_redacted_bool_passes():
    """Numbers are NOT a log channel: every numeric log attr is redacted; a bool flag passes.

    Codex Round 8 finding: trusting numeric *field names* (count/score/tokens) only moves the
    leak from nested to top-level fields.  The fix redacts ALL numeric log/​span attribute values
    regardless of key — measurements go through ``metric()`` / ``record_usage()``.  ``bool``
    (one bit, no content) under a registered flag key still passes.
    """
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    # 'score' is a numeric value (not registered as an attr key either); 'passed' is a bool flag.
    tel.log("quality.check", score=987654321, ratio=0.123456789, passed=True)
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert attrs.get("passed") is True, "registered bool flag must pass through"
    assert "987654321" not in output, "raw numeric must never appear in a log"
    assert "0.123456789" not in output, "raw float must never appear in a log"


def test_telemetry_numeric_pii_redacted():
    """Numeric PII never leaks — all numeric log values are redacted regardless of key name."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("node.complete",
            phone_number=5551234567,
            client_id=98765,
            ssn=123456789,
            count=5551234567,   # even an 'innocent' name like count must not emit the value
            score=987654321)
    output = buf.getvalue()
    assert "5551234567" not in output, "phone/count numeric value must not leak"
    assert "98765" not in output, "client_id numeric value must not leak"
    assert "123456789" not in output, "ssn numeric value must not leak"
    assert "987654321" not in output, "score numeric value must not leak"


def test_telemetry_non_finite_numeric_attr_redacted():
    """NaN / inf log attrs are redacted and never reach JSON (output stays valid JSON)."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("quality.check", score=float("nan"), confidence=float("inf"))
    output = buf.getvalue()
    json.loads(output.strip())   # must not raise — no bare NaN/Infinity tokens
    assert "NaN" not in output and "Infinity" not in output


# ---------------------------------------------------------------------------
# StdoutTelemetry — dimensions (enums/patterns), injected per agent
# ---------------------------------------------------------------------------


def test_telemetry_platform_dimension_enum_enforced():
    """A universal platform dimension (tier) accepts only its enum values."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("model.call", tier="strong")
    assert json.loads(buf.getvalue().strip())["attrs"]["tier"] == "strong"

    buf2 = io.StringIO()
    tel2 = StdoutTelemetry(stream=buf2)
    tel2.log("model.call", tier="premium_corporate")
    out2 = buf2.getvalue()
    assert json.loads(out2.strip())["attrs"]["tier"] == "[REDACTED]"
    assert "premium_corporate" not in out2


def test_telemetry_agent_dimension_requires_injection():
    """Agent-specific dimensions (node/stage) are NOT in shared core — they must be injected.

    Without injected dimensions, ``node="intake"`` is redacted (shared core has no node schema).
    With the agent's injected dimensions, a valid node value passes and an invalid one is still
    redacted.  This proves shared core is decoupled from any agent's node topology.
    """
    # No injection → 'node' is neither a shared-core dimension nor a registered attr key, so the
    # key collapses to [redacted_key] and the value is suppressed.
    buf = io.StringIO()
    bare = StdoutTelemetry(stream=buf)
    bare.log("node.complete", node="intake")
    bare_attrs = json.loads(buf.getvalue().strip()).get("attrs", {})
    assert "node" not in bare_attrs, "Shared core must not know agent node names"
    assert bare_attrs.get("[redacted_key]") == "[REDACTED]"

    # Injected → 'node' becomes a registered dimension key: valid value passes, out-of-enum redacted.
    buf2 = io.StringIO()
    agent = _tel(buf2)
    agent.log("node.complete", node="intake")
    assert json.loads(buf2.getvalue().strip())["attrs"]["node"] == "intake"

    buf3 = io.StringIO()
    agent3 = _tel(buf3)
    agent3.log("node.complete", node="client_strategy")
    out3 = buf3.getvalue()
    assert json.loads(out3.strip())["attrs"]["node"] == "[REDACTED]", (
        "An out-of-enum value must be redacted even though it is identifier-shaped"
    )
    assert "client_strategy" not in out3


def test_telemetry_identifier_shaped_user_value_redacted():
    """Identifier-shaped user content is rejected: enums reject non-members regardless of shape."""
    buf = io.StringIO()
    tel = _tel(buf)
    # node value not in the injected node enum; tier value not in the platform tier enum
    tel.log("node.complete", node="private_client_strategy", tier="premium_corporate")
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert attrs.get("node") == "[REDACTED]"
    assert attrs.get("tier") == "[REDACTED]"
    assert "private_client_strategy" not in output
    assert "premium_corporate" not in output


def test_telemetry_dimension_value_with_spaces_redacted():
    """A dimension value containing spaces is never a valid identifier — redacted."""
    buf = io.StringIO()
    tel = _tel(buf)
    tel.log("node.complete", node="my private client strategy", stage="draft review two")
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert attrs.get("node") == "[REDACTED]"
    assert attrs.get("stage") == "[REDACTED]"
    assert "my private client strategy" not in output
    assert "draft review two" not in output


# ---------------------------------------------------------------------------
# StdoutTelemetry — mapping-key sanitization (outer kwargs)
# ---------------------------------------------------------------------------


def test_telemetry_user_controlled_outer_kwarg_key_redacted():
    """A non-identifier outer kwarg key collapses to '[redacted_key]' and never appears verbatim."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("node.complete", **{"my personal field name": "some value"})
    output = buf.getvalue()
    record = json.loads(output.strip())
    assert "my personal field name" not in output
    assert record.get("attrs", {}).get("[redacted_key]") == "[REDACTED]"


def test_telemetry_identifier_shaped_user_key_redacted():
    """An identifier-shaped but UNREGISTERED key leaks neither its text nor its value.

    Codex Round 8 finding: ``private_client_strategy`` is a valid identifier, so a shape-based
    key check emitted the key text raw (value redacted, key leaked).  Keys are now authorized by
    membership in the registered key set, not by shape — unknown keys collapse to
    ``[redacted_key]`` so the sensitive key TEXT is suppressed too.
    """
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("node.complete", private_client_strategy="anything")
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert "private_client_strategy" not in output, "unregistered key text must not leak"
    assert attrs.get("[redacted_key]") == "[REDACTED]"


def test_telemetry_unregistered_dimension_key_text_redacted():
    """Open technical fields are NOT shared-core dimensions; unregistered → key text suppressed.

    Codex Round 8 example: ``{"model":"secret","region":"client-strategy","error_type":"ClientSecret"}``.
    Without per-agent injection, ``model``/``region``/``error_type`` are unregistered keys, so
    both key and value are suppressed and none of the user content is emitted.
    """
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.log("model.call", model="secret", region="client-strategy", error_type="ClientSecret")
    output = buf.getvalue()
    attrs = json.loads(output.strip()).get("attrs", {})
    assert "model" not in attrs and "region" not in attrs and "error_type" not in attrs
    assert attrs.get("[redacted_key]") == "[REDACTED]"
    for leak in ("secret", "client-strategy", "ClientSecret"):
        assert leak not in output, f"user content {leak!r} must not leak"


def test_telemetry_injected_enum_dimension_authorizes_open_field():
    """An agent can register an open technical field as a finite enum; only enum values pass."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, dimensions={"model": frozenset({"gemini-2.5-flash"})})
    tel.log("model.call", model="gemini-2.5-flash")
    assert json.loads(buf.getvalue().strip())["attrs"]["model"] == "gemini-2.5-flash"

    buf2 = io.StringIO()
    tel2 = StdoutTelemetry(stream=buf2, dimensions={"model": frozenset({"gemini-2.5-flash"})})
    tel2.log("model.call", model="secret-internal-model")
    out2 = buf2.getvalue()
    assert json.loads(out2.strip())["attrs"]["model"] == "[REDACTED]"
    assert "secret-internal-model" not in out2


# ---------------------------------------------------------------------------
# StdoutTelemetry — metric() value validation
# ---------------------------------------------------------------------------


def test_telemetry_metric_string_value_redacted():
    """metric() must reject a non-numeric value — a string value is emitted as '[REDACTED]'.

    Codex Round 7 finding: ``metric()`` wrote ``value`` straight through, so
    ``metric("llm.cost_inr", "RAW SECRET")`` leaked user content via the metric channel.
    """
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.metric("llm.cost_inr", "RAW SECRET")  # type: ignore[arg-type]
    output = buf.getvalue()
    record = json.loads(output.strip())
    assert record["value"] == "[REDACTED]", "Non-numeric metric value must be redacted"
    assert "RAW SECRET" not in output


def test_telemetry_metric_nonfinite_value_redacted():
    """metric() must reject NaN/inf; output stays valid JSON (no bare NaN/Infinity)."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        buf = io.StringIO()
        tel = StdoutTelemetry(stream=buf)
        tel.metric("llm.tokens", bad)
        output = buf.getvalue()
        record = json.loads(output.strip())   # must not raise
        assert record["value"] == "[REDACTED]", f"{bad!r} must be redacted"
        assert "NaN" not in output and "Infinity" not in output


def test_telemetry_metric_finite_value_passes():
    """A finite numeric metric value passes through unchanged."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.metric("llm.cost_inr", 12.5)
    record = json.loads(buf.getvalue().strip())
    assert record["value"] == 12.5


def test_telemetry_metric_bool_value_redacted():
    """A bool metric value is not a measurement — redacted (bool is an int subtype in Python)."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.metric("llm.tokens", True)  # type: ignore[arg-type]
    record = json.loads(buf.getvalue().strip())
    assert record["value"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# StdoutTelemetry — per-agent label extension + required DESIGN events
# ---------------------------------------------------------------------------


def test_telemetry_extra_labels_per_agent():
    """extra_labels injects per-agent event codes; shared core hardcodes no agent labels."""
    # Without injection: an agent event is blocked (not a platform label).
    buf_plain = io.StringIO()
    StdoutTelemetry(stream=buf_plain).log("intake.complete")
    assert json.loads(buf_plain.getvalue().strip())["msg"] == "[redacted_label]"

    # With injection: the agent event passes.
    buf_ext = io.StringIO()
    _tel(buf_ext).log("intake.complete")
    assert json.loads(buf_ext.getvalue().strip())["msg"] == "intake.complete"

    # Platform events always pass regardless of injection.
    buf_plat = io.StringIO()
    _tel(buf_plat).log("model.call")
    assert json.loads(buf_plat.getvalue().strip())["msg"] == "model.call"

    # Unknown events are still blocked even with injection.
    buf_bad = io.StringIO()
    _tel(buf_bad).log("user_supplied_event")
    assert json.loads(buf_bad.getvalue().strip())["msg"] == "[redacted_label]"


def test_platform_metric_names_subset_of_platform_labels():
    """_PLATFORM_METRIC_NAMES must be a strict subset of _PLATFORM_LABELS.

    Codex carry-over: metric names are measurement codes that ALSO appear in the event-label
    registry; a metric name not in _PLATFORM_LABELS would be an inconsistency in the taxonomy.
    """
    from core.providers.mock.telemetry import _PLATFORM_LABELS, _PLATFORM_METRIC_NAMES
    not_in_labels = _PLATFORM_METRIC_NAMES - _PLATFORM_LABELS
    assert not_in_labels == set(), (
        f"Every platform metric name must also be a registered platform event label. "
        f"Found in _PLATFORM_METRIC_NAMES but not in _PLATFORM_LABELS: {not_in_labels}"
    )
    assert _PLATFORM_METRIC_NAMES < _PLATFORM_LABELS, (
        "_PLATFORM_METRIC_NAMES must be a STRICT subset of _PLATFORM_LABELS "
        "(not equal — the label registry contains event codes that are not metric names)"
    )


def test_telemetry_no_agent_labels_in_shared_core():
    """Shared core must contain no agent-specific labels and only finite-enum dimensions."""
    from core.providers.mock.telemetry import _PLATFORM_LABELS, _PLATFORM_DIMENSIONS
    leaked = {lbl for lbl in _PLATFORM_LABELS if lbl.split(".")[0] in {
        "intake", "transcribe", "normalize", "extract", "plan", "draft", "review", "finalize",
    }}
    assert leaked == set(), f"Agent-specific labels leaked into shared core: {leaked}"
    # Junk/utility labels must be gone too.
    for junk in ("x", "m", "hello", "auth", "processing", "node", "msg", "event"):
        assert junk not in _PLATFORM_LABELS, f"junk label {junk!r} must not be a platform label"
    # node/stage are agent dimensions, and open technical fields are injected — NOT hardcoded.
    for agent_or_open in ("node", "stage", "model", "region", "version", "error_type", "error_code"):
        assert agent_or_open not in _PLATFORM_DIMENSIONS, (
            f"{agent_or_open!r} must be injected per agent, not a shared-core dimension"
        )
    # Every platform dimension must be a finite enum (frozenset) — no regex-authorized values.
    for key, schema in _PLATFORM_DIMENSIONS.items():
        assert isinstance(schema, frozenset), f"dimension {key!r} must be a finite enum, not a pattern"


def test_telemetry_design_events_registered():
    """Required DESIGN §11 platform events must be registered and emit as-is."""
    for event_code in ("model.call", "model.response", "model.error",
                       "tool.call", "tool.result", "tool.error",
                       "route.decision"):
        buf = io.StringIO()
        StdoutTelemetry(stream=buf).log(event_code)
        record = json.loads(buf.getvalue().strip())
        assert record["msg"] == event_code, (
            f"Required DESIGN §11 event '{event_code}' must be registered, not redacted"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_factory_selects_mock_offline():
    assert isinstance(get_llm_provider({"llm": {"provider": "mock"}}), MockLLMProvider)
    assert isinstance(get_transcription_provider({"transcription": {"provider": "mock"}}), MockTranscriptionProvider)
    assert isinstance(get_object_storage({}), InMemoryObjectStorage)
    assert isinstance(get_secret_store({}), EnvSecretStore)
    assert isinstance(get_telemetry({}), StdoutTelemetry)


@pytest.mark.parametrize("provider", ["bedrock", "azure"])
def test_factory_cloud_returns_interface_complete_stub(provider):
    """Increment 7: bedrock/azure now resolve to interface-complete stubs.

    The factory CONSTRUCTS the stub (it satisfies the ABC and is indistinguishable from a wired
    backend at construction); the loud NotImplementedError fires only when a method is CALLED.
    Previously the factory raised at selection time — that contract was replaced so config-only
    swap is testable and "going live" is a body-fill, not a redesign (DESIGN §4.2/§12).
    """
    stub = get_llm_provider({"llm": {"provider": provider, "tier_models": {"cheap": "x", "strong": "y"}}})
    assert isinstance(stub, LLMProvider)
    assert stub.name in ("bedrock", "azure")
    with pytest.raises(NotImplementedError):
        stub.respond([{"role": "user", "content": "hi"}], tier="cheap")


def test_factory_telemetry_wires_extra_labels_and_dimensions():
    """get_telemetry must wire telemetry.extra_labels + telemetry.dimensions from config.

    Codex Round 7 finding: the per-agent extension mechanism was not operational through the
    config-driven factory.  An agent declares its labels/dimensions in config; the factory must
    pass them to StdoutTelemetry so they take effect.
    """
    cfg = {
        "telemetry": {
            "provider": "stdout",
            "extra_labels": ["intake.complete"],
            "dimensions": {"node": ["intake", "draft"]},
            "attr_keys": ["chunk_flag"],
        }
    }
    tel = get_telemetry(cfg)
    assert isinstance(tel, StdoutTelemetry)

    buf = io.StringIO()
    tel._stream = buf  # redirect the configured instance for assertion
    tel.log("intake.complete", node="intake", chunk_flag=True)
    record = json.loads(buf.getvalue().strip())
    assert record["msg"] == "intake.complete", "config extra_labels must be wired"
    assert record["attrs"]["node"] == "intake", "config dimensions must be wired"
    assert record["attrs"]["chunk_flag"] is True, "config attr_keys must be wired"

    # A node value outside the configured enum is still redacted.
    buf2 = io.StringIO()
    tel._stream = buf2
    tel.log("intake.complete", node="client_strategy")
    assert json.loads(buf2.getvalue().strip())["attrs"]["node"] == "[REDACTED]"


def test_factory_telemetry_wires_extra_metric_names():
    """get_telemetry must wire telemetry.extra_metric_names from config.

    Codex Round 9: metric() now uses a separate metric-name registry.  Agents register custom
    metric names via config so only those names may emit raw numeric values.
    """
    cfg = {
        "telemetry": {
            "extra_metric_names": ["agent.total_cost_inr"],
        }
    }
    tel = get_telemetry(cfg)
    assert isinstance(tel, StdoutTelemetry)

    buf = io.StringIO()
    tel._stream = buf
    tel.metric("agent.total_cost_inr", 25.5)
    record = json.loads(buf.getvalue().strip())
    assert record["name"] == "agent.total_cost_inr", "config extra_metric_names must be wired"
    assert record["value"] == 25.5, "registered metric name must allow a finite value"

    # An unregistered metric name (even if plausible) still redacts the value.
    buf2 = io.StringIO()
    tel._stream = buf2
    tel.metric("agent.unregistered_metric", 99.9)
    record2 = json.loads(buf2.getvalue().strip())
    assert record2["value"] == "[REDACTED]"
    assert "99.9" not in buf2.getvalue()


# ---------------------------------------------------------------------------
# StdoutTelemetry — metric() name registry (separate from event-label registry)
# ---------------------------------------------------------------------------


def test_telemetry_unregistered_metric_name_redacts_value():
    """An unregistered metric name cannot emit a raw numeric value.

    Codex Round 9 finding: metric() used the broad event-label registry, so
    ``metric("node.complete", 5551234567)`` produced
    ``{"name":"[redacted_label]","value":5551234567}`` — leaking user-controlled numeric content
    through a channel that had no attribute-level redaction.  Fix: metric names use their OWN
    separate registry (_PLATFORM_METRIC_NAMES); if the name is not registered, the value is also
    redacted.  A raw number cannot pass through an unknown name.
    """
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.metric("node.complete", 5551234567)   # event label, NOT a metric name
    record = json.loads(buf.getvalue().strip())
    assert record["name"] == "[redacted_label]"
    assert record["value"] == "[REDACTED]", (
        "value must be redacted when metric name is not registered"
    )
    assert "5551234567" not in buf.getvalue(), "raw numeric must not appear via unregistered metric name"


def test_telemetry_arbitrary_metric_name_redacts_value():
    """An arbitrary unregistered string cannot carry a numeric value through metric()."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.metric("user_controlled_metric", 42.0)
    record = json.loads(buf.getvalue().strip())
    assert record["name"] == "[redacted_label]"
    assert record["value"] == "[REDACTED]"
    # Check the JSON value field specifically — not the whole buffer, which may contain
    # "42" incidentally (e.g. in a randomly-generated trace_id).
    assert record.get("value") != 42 and record.get("value") != 42.0


def test_telemetry_registered_platform_metric_name_passes_value():
    """A registered platform metric name emits its finite numeric value unchanged."""
    for name in ("llm.cost_inr", "llm.tokens", "stt.cost_inr",
                 "stt.audio_seconds", "stage.cost_inr", "total.cost_inr"):
        buf = io.StringIO()
        tel = StdoutTelemetry(stream=buf)
        tel.metric(name, 12.5)
        record = json.loads(buf.getvalue().strip())
        assert record["name"] == name, f"{name!r} must be a registered platform metric name"
        assert record["value"] == 12.5


def test_telemetry_injected_metric_name_authorizes_value():
    """An agent can inject custom metric names; only those names may emit raw numeric values."""
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf, extra_metric_names=frozenset({"agent.total_cost_inr"}))
    tel.metric("agent.total_cost_inr", 25.5)
    record = json.loads(buf.getvalue().strip())
    assert record["name"] == "agent.total_cost_inr"
    assert record["value"] == 25.5

    # A name NOT in the injected extra set is still blocked.
    buf2 = io.StringIO()
    tel2 = StdoutTelemetry(stream=buf2, extra_metric_names=frozenset({"agent.total_cost_inr"}))
    tel2.metric("agent.secret_metric", 99.9)
    record2 = json.loads(buf2.getvalue().strip())
    assert record2["name"] == "[redacted_label]"
    assert record2["value"] == "[REDACTED]"
    assert "99.9" not in buf2.getvalue()


def test_telemetry_platform_event_label_not_a_metric_name():
    """Platform event labels (e.g. 'node.complete') are NOT valid metric names.

    The metric-name registry is a strict subset of the event-label registry.  Using an event
    label as a metric name must not authorize a raw numeric value.
    """
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    # These are all registered event labels, but none are registered metric names.
    for event_label in ("node.complete", "graph.started", "quality.check", "route.decision"):
        buf2 = io.StringIO()
        tel2 = StdoutTelemetry(stream=buf2)
        tel2.metric(event_label, 12345.0)
        record = json.loads(buf2.getvalue().strip())
        assert record["value"] == "[REDACTED]", (
            f"event label {event_label!r} must not authorize a numeric value through metric()"
        )
        assert record["value"] != 12345.0
        assert record["value"] != "12345.0"


# ---------------------------------------------------------------------------
# StdoutTelemetry — record_usage() runtime validation
# ---------------------------------------------------------------------------


def test_record_usage_rejects_duck_typed_object():
    """record_usage() must reject a non-Usage duck-typed object (e.g. a plain dict).

    Codex Round 9 finding: record_usage() trusted any duck-typed object, so a plain dict like
    ``{"prompt_tokens": "RAW PROMPT SECRET", ...}`` was emitted verbatim via attribute access.
    Fix: require isinstance(usage, Usage); a non-Usage object emits a minimal safe error record.
    """
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.record_usage(  # type: ignore[arg-type]
        {"prompt_tokens": "RAW PROMPT SECRET", "completion_tokens": "RAW OUTPUT SECRET",
         "cost_native": "RAW COST SECRET"}
    )
    output = buf.getvalue()
    record = json.loads(output.strip())
    assert record.get("error") == "invalid_usage_type", (
        "duck-typed object must produce an error record, not emit raw field values"
    )
    assert "RAW PROMPT SECRET" not in output
    assert "RAW OUTPUT SECRET" not in output
    assert "RAW COST SECRET" not in output
    # Sensitive field names themselves must not appear in the emitted record.
    assert "prompt_tokens" not in record or record["prompt_tokens"] != "RAW PROMPT SECRET"


def test_record_usage_rejects_model_construct_bypass():
    """record_usage() must catch Usage.model_construct() bypass via model_validate(model_dump()).

    ``model_construct()`` skips Pydantic validators, allowing invalid field values (e.g. a string
    for an int field).  record_usage() re-validates the dumped fields so this bypass is caught.
    """
    from core import Usage
    # model_construct bypasses the ge=0 / int validators on prompt_tokens.
    bad_usage = Usage.model_construct(prompt_tokens="RAW PROMPT SECRET")
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.record_usage(bad_usage)
    output = buf.getvalue()
    record = json.loads(output.strip())
    assert record.get("error") in ("invalid_usage_type", "invalid_usage_fields"), (
        "model_construct()-bypassed Usage must be caught by revalidation"
    )
    assert "RAW PROMPT SECRET" not in output, "bypassed field value must not leak"


def test_record_usage_accepts_valid_usage():
    """A valid Usage instance is accepted and its validated fields are emitted normally."""
    from core import Usage
    usage = Usage(prompt_tokens=10, completion_tokens=5, synthetic=True)
    buf = io.StringIO()
    tel = StdoutTelemetry(stream=buf)
    tel.record_usage(usage)
    record = json.loads(buf.getvalue().strip())
    assert record["event"] == "usage"
    assert record["prompt_tokens"] == 10
    assert record["completion_tokens"] == 5
    assert record["synthetic"] is True
    assert "error" not in record, "valid Usage must not produce an error record"
