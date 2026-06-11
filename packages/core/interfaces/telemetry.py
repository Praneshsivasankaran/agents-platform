"""Telemetry — observability seam (DESIGN §11).

Cloud-neutral: structured JSON spans/logs/metrics in dev; OpenTelemetry export in prod. Emits
per-node spans, per-stage token/cost metrics, quality metrics, and route/error events — with
sensitive payloads redacted (DESIGN §10). The same interface is used on every cloud.

Cloud-neutral by construction: imports only the shared ``Usage`` contract + the standard library.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any

from .usage import Usage


class Telemetry(ABC):
    """Abstract telemetry sink. The concrete stdout-JSON impl is promoted from the bake-off."""

    @abstractmethod
    def log(self, msg: str, **fields: Any) -> None:
        """Emit a structured log event (sensitive fields must be redacted by the impl)."""
        raise NotImplementedError

    @abstractmethod
    def metric(self, name: str, value: float, **tags: Any) -> None:
        """Emit a single metric sample.

        ``name`` MUST be a statically registered metric name (``_PLATFORM_METRIC_NAMES`` ∪ any
        agent-injected ``extra_metric_names``). A raw numeric value cannot pass through an unknown
        name — implementations must redact the value when the name is not registered.  Metric names
        are a STRICT SUBSET of event labels; general event codes (e.g. ``"node.complete"``) are
        NOT valid metric names.  ``value`` must be a finite real number (``bool``, ``NaN``, ``inf``
        are rejected).  Examples of registered platform metric names: ``"llm.cost_inr"``,
        ``"llm.tokens"``, ``"stt.cost_inr"``, ``"stage.cost_inr"``, ``"total.cost_inr"``.
        """
        raise NotImplementedError

    @abstractmethod
    def record_usage(self, usage: Usage, **tags: Any) -> None:
        """Record token/cost usage — the shared ``Usage`` contract — from an ``LLMProvider`` /
        ``TranscriptionProvider`` call; emits token + provider-native cost metrics (DESIGN §11).

        Implementations MUST require an actual ``Usage`` instance (not a duck-typed object) and
        MUST re-validate the object via ``Usage.model_validate(usage.model_dump())`` to catch
        instances created through ``Usage.model_construct()`` that may have bypassed field
        validators.  An invalid or unrecognised argument must emit a minimal safe error record;
        raw field values from an untrusted object must never be emitted.
        """
        raise NotImplementedError

    @abstractmethod
    def span(self, name: str, **attrs: Any) -> AbstractContextManager[str]:
        """Return a context manager wrapping one unit of work (a LangGraph node); yields a span id.

        Concrete impls implement this with ``contextlib.contextmanager`` (DESIGN §11).
        """
        raise NotImplementedError
