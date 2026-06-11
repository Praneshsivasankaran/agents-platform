"""StdoutTelemetry — cloud-neutral structured-JSON Telemetry for dev/CI.

Emits one JSON object per line (span_start/span_end/log/metric/usage) with a run-level trace
id.  Production exports the same shape via OpenTelemetry (later).  NOT agent logic.

Security model (DESIGN §10) — registered, not inferred
======================================================
Telemetry is a channel for **developer-authored, registered metadata only**.  Nothing about a
caller-supplied key or value is trusted because of how it *looks* (a regex, a length, a numeric
type, a field name).  Provenance is established by **explicit registration**, and everything
unregistered is redacted.  Concretely:

1.  **Registered labels.**  Every ``msg`` (log), metric ``name``, and span name must be a member
    of the instance label set (``_PLATFORM_LABELS | extra_labels``).  Non-members become
    ``"[redacted_label]"``.  Agent event codes are injected at construction; shared core ships
    only a small platform taxonomy and contains no per-agent labels.

2.  **Registered attribute keys.**  An attribute key is emitted only if it is in the instance's
    registered key set (``_PLATFORM_ATTR_KEYS`` ∪ sensitive keys ∪ dimension keys ∪ injected
    ``attr_keys``).  Any other key — including identifier-shaped user content like
    ``private_client_strategy`` — collapses to ``"[redacted_key]": "[REDACTED]"``.  Keys are
    matched by membership, not by shape.

3.  **Dimensions are finite enums, injected per agent.**  A string value is emitted only when
    its key has a registered dimension *enum* and the value is a member of it.  Universal
    dimensions (``tier``, ``cloud``, ``env``, ``status`` …) ship in ``_PLATFORM_DIMENSIONS``.
    Agent-specific dimensions (``node``, ``stage`` …) and open technical fields (``model``,
    ``region`` …) are **injected** as enums by the agent/config — there are no regex-authorized
    dimensions, because a regex proves shape, not trusted provenance.

4.  **Numerics are not a log channel.**  Every ``int``/``float`` attribute value in ``log()`` /
    ``span()`` / ``record_usage(**tags)`` is redacted (``"[REDACTED]"``) regardless of key —
    numeric PII (phone numbers, ids) is indistinguishable from a "count" by value.  Real
    measurements go through ``metric(name, value)`` (finite-validated) or ``record_usage()``
    (Usage-contract-validated).  ``bool`` (one bit, no content) and ``None`` (JSON null) pass.

5.  **Nested structures are opaque.**  A Mapping, list, tuple, Pydantic model, or arbitrary
    object is redacted wholesale to ``"[REDACTED]"`` — never walked.

6.  **Known-sensitive keys** (``_SENSITIVE_KEYS_LOWER``) are always ``"[REDACTED]"``.

7.  **metric() validates name AND value.**  The name must be a member of the registered
    metric-name set (``_PLATFORM_METRIC_NAMES ∪ extra_metric_names``) — a broader event label
    such as ``"node.complete"`` is NOT a valid metric name.  If the name is unregistered the
    value is also redacted (a raw number cannot pass through an unknown name).  The value must
    be a finite real (no ``bool``, no ``NaN``/``inf``); invalid values become ``"[REDACTED]"``.

8.  **record_usage() runtime-validates its argument.**  ``usage`` must be an actual ``Usage``
    instance (not a duck-typed object) and is re-validated via
    ``Usage.model_validate(usage.model_dump())`` to catch instances created through
    ``Usage.model_construct()`` that bypassed field validators.  An invalid or unrecognised
    object emits a minimal safe error record — raw field values are never emitted.

9.  **Strict serialization.**  ``json.dumps(..., allow_nan=False)`` rejects non-finite floats;
    a record that fails to serialize is replaced by a minimal safe record (no repr leakage).

10. **Reserved structural keys** are stripped from caller kwargs (case-insensitive) first.
"""

from __future__ import annotations

import json
import math
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable

from ...interfaces import Telemetry, Usage

# ---------------------------------------------------------------------------
# Registered-label taxonomy (platform-level; agent events injected separately)
# ---------------------------------------------------------------------------

#: Platform-level event taxonomy shared by all agents.  Intentionally small and generic — it
#: contains NO agent-specific node/stage events and NO test/utility junk labels.  Agents inject
#: their own event codes via the ``extra_labels`` constructor parameter (wired through the
#: factory from config: ``telemetry.extra_labels``).
_PLATFORM_LABELS: frozenset[str] = frozenset({
    # Graph lifecycle
    "graph.started",    "graph.complete",    "graph.error",
    # Node lifecycle (generic; specific node *names* are dimensions, not labels)
    "node.started",     "node.complete",     "node.error",
    # Model / tool / routing (DESIGN §11)
    "model.call",       "model.response",    "model.error",
    "tool.call",        "tool.result",       "tool.error",
    "route.decision",
    # Provider lifecycle
    "provider.call",    "provider.response", "provider.error",
    # Cost gate
    "cost.gate.check",  "cost.gate.passed",  "cost.gate.blocked",  "cost.check",
    # Quality gate (the reference quality loop all agents copy)
    "quality.check",
    "quality.review.passed", "quality.review.failed", "quality.escalated",
    # Standard metric names
    "llm.cost_inr",   "llm.tokens",
    "stt.cost_inr",   "stt.audio_seconds",
    "stage.cost_inr", "total.cost_inr",
})

#: Metric-name registry — a STRICT SUBSET of ``_PLATFORM_LABELS`` containing only actual numeric
#: measurement codes.  ``metric()`` validates names against THIS set, not the broader event-label
#: registry, so a general event code such as ``"node.complete"`` cannot authorize a raw numeric
#: value.  Agent-specific metric names are injected via ``extra_metric_names`` (wired by the
#: factory from ``telemetry.extra_metric_names`` in config).
_PLATFORM_METRIC_NAMES: frozenset[str] = frozenset({
    "llm.cost_inr",   "llm.tokens",
    "stt.cost_inr",   "stt.audio_seconds",
    "stage.cost_inr", "total.cost_inr",
})

#: Maximum label length — applied before the registry membership check.
_MAX_LABEL_LEN: int = 64

# ---------------------------------------------------------------------------
# Sensitive-key denylist (checked first, before any allowlist logic)
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS_LOWER: frozenset[str] = frozenset({
    "text", "content", "prompt", "transcript", "draft", "raw_input",
    "input", "output", "secret", "api_key", "token", "password",
    "authorization", "access_token", "client_secret", "credentials",
    "headers", "cookies",
})

# ---------------------------------------------------------------------------
# Registered attribute keys (platform-level; agent keys injected separately)
# ---------------------------------------------------------------------------

#: Boolean-flag attribute names the platform recognizes.  Only ``bool`` values are meaningful
#: here (a bool carries one bit, no content); a non-bool value under one of these keys is still
#: type-gated by ``_redact_value`` (numeric → redacted, string → needs a dimension enum).  This
#: set deliberately contains NO numeric-measurement names — numbers are not a log channel
#: (see rule 4); measurements go through ``metric()`` / ``record_usage()``.
_PLATFORM_ATTR_KEYS: frozenset[str] = frozenset({
    "passed", "failed", "retried", "ok", "cached", "truncated", "escalated",
})

# ---------------------------------------------------------------------------
# Dimension enums — per-key finite value sets; agent dimensions are injected
# ---------------------------------------------------------------------------

#: Universal, low-cardinality dimensions shared by every agent — finite enums ONLY.  There are
#: deliberately no regex-authorized dimensions: a pattern proves shape, not that a value came
#: from trusted configuration.  Agent-specific dimensions (``node``, ``stage``) and open
#: technical fields (``model``, ``region``, ``version`` …) are supplied per agent via the
#: ``dimensions`` constructor parameter as finite enums declared in config.
_PLATFORM_DIMENSIONS: dict[str, frozenset[str]] = {
    "tier":     frozenset({"cheap", "strong"}),
    "cloud":    frozenset({"gcp", "aws", "azure", "mock"}),
    "provider": frozenset({"mock", "gcp", "bedrock", "azure", "litellm", "vertex"}),
    "env":      frozenset({"prod", "staging", "dev", "test", "ci"}),
    "status":   frozenset({"pass", "fail", "error", "skip", "pending", "complete", "ok"}),
    "action":   frozenset({"retry", "escalate", "skip", "abort", "continue"}),
    "language": frozenset({
        "en", "es", "fr", "de", "ja", "zh", "pt", "ar",
        "ru", "it", "ko", "nl", "pl", "sv", "tr",
        "zh-cn", "zh-tw", "pt-br",
    }),
    "format":   frozenset({"json", "yaml", "csv", "txt", "md", "html", "xml"}),
}


def _validate_dimension(key: str, value: str, dimensions: dict[str, frozenset[str]]) -> bool:
    """Return True iff ``value`` is a member of the registered enum for ``key``.

    Returns False for any key without a registered dimension enum (default-closed): a string
    under an unregistered dimension key is always redacted.
    """
    enum = dimensions.get(key)
    return enum is not None and value in enum

# ---------------------------------------------------------------------------
# Reserved structural keys (stripped from caller kwargs before redaction)
# ---------------------------------------------------------------------------

_RESERVED_KEYS_LOWER: frozenset[str] = frozenset({
    "event", "trace_id", "span_id", "span", "timestamp", "level",
    "service", "msg", "name", "value", "duration_ms",
    "prompt_tokens", "completion_tokens", "audio_seconds",
    "cost_native", "currency", "synthetic",
})


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------


def _sanitize_label(s: str, registered: frozenset[str]) -> str:
    """Return ``s`` if it is a registered event code, else ``"[redacted_label]"``.

    Truncates to ``_MAX_LABEL_LEN`` and strips control characters first.  Membership in
    ``registered`` (not a regex) is the authority — a bare lowercase word like ``"secret"``
    that satisfies an identifier regex is still rejected unless it is in the registry.
    """
    cleaned = str(s)[:_MAX_LABEL_LEN].replace("\n", "").replace("\r", "").replace("\0", "")
    return cleaned if cleaned in registered else "[redacted_label]"


def _redact_value(value: Any, key: str | None, dimensions: dict[str, frozenset[str]]) -> Any:
    """Fail-closed scalar redaction for one attribute value (NO recursion).

    Order:
      1. Known-sensitive key                  -> "[REDACTED]"
      2. None                                  -> None
      3. bool (one bit, no content)            -> passes
      4. int/float                             -> "[REDACTED]" (numbers are not a log channel)
      5. str: key has a dimension enum the
         value is a member of                  -> passes; else "[REDACTED]"
      6. Mapping / list / tuple / model / obj  -> "[REDACTED]" (opaque, never walked)
    """
    str_key = key.lower() if isinstance(key, str) else None

    if str_key is not None and str_key in _SENSITIVE_KEYS_LOWER:
        return "[REDACTED]"
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return "[REDACTED]"
    if isinstance(value, str):
        if str_key is not None and _validate_dimension(str_key, value, dimensions):
            return value
        return "[REDACTED]"
    # Mapping, list, tuple, Pydantic model, or any arbitrary object: opaque → redact wholesale.
    return "[REDACTED]"


def _safe_attrs(
    fields: dict[str, Any],
    attr_keys: frozenset[str],
    dimensions: dict[str, frozenset[str]],
) -> dict[str, Any]:
    """Process caller kwargs for safe emission, nested under ``{"attrs": ...}``.

    1. Strip reserved structural keys (case-insensitive).
    2. A key is emitted only if it is REGISTERED (``attr_keys`` membership, case-insensitive);
       any other key collapses to ``"[redacted_key]": "[REDACTED]"`` — keys are never accepted
       by shape.
    3. Each value is redacted by ``_redact_value`` (scalars only; numbers and structures opaque).
    Returns ``{}`` when nothing remains.
    """
    user = {k: v for k, v in fields.items() if k.lower() not in _RESERVED_KEYS_LOWER}
    if not user:
        return {}
    result: dict[str, Any] = {}
    for k, v in user.items():
        if isinstance(k, str) and k.lower() in attr_keys:
            result[k] = _redact_value(v, k, dimensions)
        else:
            result["[redacted_key]"] = "[REDACTED]"
    return {"attrs": result}


# ---------------------------------------------------------------------------
# StdoutTelemetry
# ---------------------------------------------------------------------------


class StdoutTelemetry(Telemetry):
    """Structured JSON telemetry sink (stdout or injected stream).

    Parameters
    ----------
    service:
        Service-name label stamped on every record.
    stream:
        Output stream (defaults to ``sys.stdout``).  Inject ``io.StringIO`` in tests.
    extra_labels:
        Per-agent event codes added to the platform taxonomy (factory: ``telemetry.extra_labels``).
    dimensions:
        Per-agent dimension enums merged over ``_PLATFORM_DIMENSIONS`` (factory:
        ``telemetry.dimensions``).  Maps a dimension key (e.g. ``"node"``) to a ``frozenset`` of
        its allowed values.  String attribute values pass only when their key has an enum here
        that the value is a member of.  Registering a dimension key also registers it as an
        emittable attribute key.
    attr_keys:
        Per-agent registered attribute keys for non-dimension scalar attributes the agent emits
        (factory: ``telemetry.attr_keys``).  Keys not registered anywhere collapse to
        ``"[redacted_key]"``.
    extra_metric_names:
        Per-agent metric names added to the platform metric-name registry (factory:
        ``telemetry.extra_metric_names``).  Only names in this set (union ``_PLATFORM_METRIC_NAMES``)
        may carry a raw numeric value through ``metric()``.
    _trace_id / _clock / _span_id_factory:
        Test-only deterministic injectors.
    """

    def __init__(
        self,
        service: str = "agents-platform",
        stream: Any = None,
        *,
        extra_labels: "frozenset[str] | None" = None,
        dimensions: "dict[str, frozenset[str]] | None" = None,
        attr_keys: "frozenset[str] | None" = None,
        extra_metric_names: "frozenset[str] | None" = None,
        _trace_id: "str | None" = None,
        _clock: "Callable[[], float] | None" = None,
        _span_id_factory: "Callable[[], str] | None" = None,
    ) -> None:
        self.service = service
        self._stream = stream if stream is not None else sys.stdout
        self.trace_id: str = _trace_id if _trace_id is not None else uuid.uuid4().hex[:16]
        self._clock: Callable[[], float] = _clock if _clock is not None else time.perf_counter
        self._span_id_factory: Callable[[], str] = (
            _span_id_factory if _span_id_factory is not None
            else lambda: uuid.uuid4().hex[:8]
        )
        self._labels: frozenset[str] = (
            _PLATFORM_LABELS | extra_labels if extra_labels else _PLATFORM_LABELS
        )
        if dimensions:
            merged = dict(_PLATFORM_DIMENSIONS)
            merged.update(dimensions)
            self._dimensions: dict[str, frozenset[str]] = merged
        else:
            self._dimensions = _PLATFORM_DIMENSIONS
        # Registered attribute keys: platform flags ∪ sensitive (so their keys show with a
        # redacted value) ∪ dimension keys ∪ injected agent keys — all lowercased.
        self._attr_keys: frozenset[str] = frozenset(
            k.lower()
            for k in (
                _PLATFORM_ATTR_KEYS
                | _SENSITIVE_KEYS_LOWER
                | set(self._dimensions)
                | (attr_keys or frozenset())
            )
        )
        # Registered metric names: platform measurements ∪ injected per-agent names.  Separate
        # from the event-label registry so that a general event code (e.g. "node.complete")
        # cannot authorize a raw numeric value through metric().
        self._metric_names: frozenset[str] = _PLATFORM_METRIC_NAMES | (extra_metric_names or frozenset())

    def _emit(self, obj: dict[str, Any]) -> None:
        """Write one JSON record with strict serialization.

        ``allow_nan=False`` rejects non-finite floats (invalid JSON).  If a record fails to
        serialize for any reason, a minimal safe record is emitted instead of crashing the
        caller or leaking a repr via a fallback serializer.
        """
        record: dict[str, Any] = {"trace_id": self.trace_id, "service": self.service}
        record.update(obj)
        try:
            line = json.dumps(record, allow_nan=False)
        except (ValueError, TypeError):
            line = json.dumps(
                {
                    "trace_id": self.trace_id,
                    "service": self.service,
                    "event": record.get("event", "log"),
                    "error": "unserializable_record",
                },
                allow_nan=False,
            )
        self._stream.write(line + "\n")

    def log(self, msg: str, **fields: Any) -> None:
        """Emit a log event.  ``msg`` must be a registered label."""
        self._emit({
            "event": "log",
            "msg": _sanitize_label(msg, self._labels),
            **_safe_attrs(fields, self._attr_keys, self._dimensions),
        })

    def metric(self, name: str, value: float, **tags: Any) -> None:
        """Emit a metric sample.

        ``name`` must be a registered metric name (``_PLATFORM_METRIC_NAMES | extra_metric_names``).
        Note: metric names are a strict subset of event labels — a general event code such as
        ``"node.complete"`` is NOT a registered metric name.  If the name is unregistered, the
        value is also redacted: a raw numeric value cannot pass through an unknown name.
        ``value`` must be a finite real (no ``bool``, no ``NaN``/``inf``).
        """
        safe_name = _sanitize_label(name, self._metric_names)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            safe_value: Any = "[REDACTED]"
        elif safe_name == "[redacted_label]":
            # Unregistered name → redact value too; a raw number cannot pass through an unknown name.
            safe_value = "[REDACTED]"
        else:
            safe_value = value
        self._emit({
            "event": "metric",
            "name": safe_name,
            "value": safe_value,
            **_safe_attrs(tags, self._attr_keys, self._dimensions),
        })

    def record_usage(self, usage: Usage, **tags: Any) -> None:
        """Record token/cost usage from an LLM or STT call.

        ``usage`` must be a real ``Usage`` instance (not a duck-typed object).  Fields are
        re-validated via ``Usage.model_validate(usage.model_dump())`` to catch instances created
        through ``Usage.model_construct()`` that may have bypassed field validators (e.g. a string
        in a numeric field).  An invalid or unrecognised object emits a minimal safe error record;
        raw field values from an untrusted object are never emitted.
        """
        if not isinstance(usage, Usage):
            self._emit({
                "event": "usage",
                "error": "invalid_usage_type",
                **_safe_attrs(tags, self._attr_keys, self._dimensions),
            })
            return
        try:
            # warnings=False: suppress Pydantic's PydanticSerializationUnexpectedValue noise when
            # dumping a model_construct()-bypassed instance — model_validate below will properly
            # reject any field-type violations; the serialization warning adds no value here.
            validated = Usage.model_validate(usage.model_dump(warnings=False))
        except Exception:
            self._emit({
                "event": "usage",
                "error": "invalid_usage_fields",
                **_safe_attrs(tags, self._attr_keys, self._dimensions),
            })
            return
        self._emit({
            "event": "usage",
            "prompt_tokens": validated.prompt_tokens,
            "completion_tokens": validated.completion_tokens,
            "audio_seconds": validated.audio_seconds,
            "cost_native": validated.cost_native,
            "currency": validated.currency,
            "synthetic": validated.synthetic,
            **_safe_attrs(tags, self._attr_keys, self._dimensions),
        })

    @contextmanager
    def span(self, name: str, **attrs: Any):
        """Context manager wrapping one unit of work.  Yields the span id.

        ``name`` must be a registered label; ``**attrs`` are redacted and nested under ``attrs``.
        """
        span_id = self._span_id_factory()
        t0 = self._clock()
        self._emit({
            "event": "span_start",
            "span": _sanitize_label(name, self._labels),
            "span_id": span_id,
            **_safe_attrs(attrs, self._attr_keys, self._dimensions),
        })
        try:
            yield span_id
        finally:
            self._emit({
                "event": "span_end",
                "span": _sanitize_label(name, self._labels),
                "span_id": span_id,
                "duration_ms": round((self._clock() - t0) * 1000, 3),
            })
