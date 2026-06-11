"""LLMProvider — the platform's single model seam.

Agent logic depends on this abstract interface, NEVER on a cloud SDK or a vendor model name.
Concrete implementations (Mock for offline tests, a LiteLLM-backed provider for GCP/Vertex
first, AWS Bedrock + Azure as stubs) are selected by config through the provider factory
(``core.factory``). See DESIGN.md §3, §4, §8.

Typed I/O per the platform rule: Pydantic. Cloud-neutral by construction — imports only
Pydantic + the standard library; never a cloud SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field, SerializeAsAny, model_validator

from .base import CoreContractModel, ToolArgs, assert_deeply_immutable
from .usage import Usage

# Agent logic asks for a *tier*; the concrete vendor model is resolved from config
# (DESIGN §8.3). It never names a vendor model inline.
Tier = Literal["cheap", "strong"]


class ToolCall(CoreContractModel):
    """A requested tool invocation. ``args`` is a **JSON-only, deeply-immutable** mapping: values
    are restricted to ``str``/``int``/``float``/``bool``/``None``/lists/objects (no ``set``, no
    Pydantic models, no non-finite floats); it is read-only at every level and serializes back to a
    plain dict (pickle/checkpoint-safe). See ``core.interfaces.base.ToolArgs``."""

    name: str
    args: ToolArgs = Field(default_factory=dict, validate_default=True)


class LLMResponse(CoreContractModel):
    """One model response carrying **exactly one** payload channel.

    Immutable + strict + copy-safe (via ``CoreContractModel``): cannot be mutated, rejects unknown
    fields, and ``model_copy(update=...)`` revalidates — so a text response cannot be copied into a
    multi-payload one.

    Exactly one of ``text`` / ``tool_call`` / ``structured`` is populated (errors are not a payload;
    they surface via the graph's ``error_state``).

    ``structured`` holds a **validated instance of the requested ``response_schema``**, annotated
    ``SerializeAsAny[BaseModel]`` so ``model_dump()`` emits the concrete subclass's fields. To be
    immutable in depth (not just frozen at the top), a structured payload **must subclass
    ``CoreContractModel`` and use immutable nested field types** (``tuple[...]`` / nested
    ``CoreContractModel``); this is enforced below via ``assert_deeply_immutable``.

    **Provider contract:** when a ``response_schema`` is requested, implementations MUST build the
    response via :meth:`structured_from`. Direct ``structured=`` is only for objects already
    validated against the requested (deeply-immutable) schema. TODO(Increment 2): provider
    conformance tests MUST assert schema mismatch is rejected and providers route through
    ``structured_from``.
    """

    text: str | None = None
    tool_call: ToolCall | None = None
    structured: SerializeAsAny[BaseModel] | None = None
    usage: Usage = Field(default_factory=Usage)

    @model_validator(mode="after")
    def _validate_payload(self) -> "LLMResponse":
        populated = [self.text is not None, self.tool_call is not None, self.structured is not None]
        if sum(populated) != 1:
            raise ValueError(
                "LLMResponse must carry exactly one payload — set exactly one of "
                f"`text`, `tool_call`, or `structured` (got {sum(populated)})."
            )
        if self.structured is not None:
            if not isinstance(self.structured, CoreContractModel):
                raise ValueError(
                    "LLMResponse.structured must be a CoreContractModel subclass (frozen + "
                    "extra=forbid) so the validated structured payload is immutable."
                )
            # Reject mutable nested containers (list/dict/set) — frozen is only shallow.
            assert_deeply_immutable(self.structured)
        return self

    @classmethod
    def structured_from(
        cls,
        response_schema: type[CoreContractModel],
        raw: object,
        *,
        usage: "Usage | None" = None,
    ) -> "LLMResponse":
        """Build a structured response, **validating** ``raw`` against ``response_schema``.

        ``response_schema.model_validate(raw)`` raises on mismatch, so the resulting ``structured``
        is guaranteed to be a validated instance of ``response_schema``. The schema must be a
        deeply-immutable ``CoreContractModel`` (see class docstring). Provider implementations MUST
        construct structured responses via this helper whenever a ``response_schema`` is requested —
        never by assigning ``structured=`` to unvalidated data.
        """
        validated = response_schema.model_validate(raw)
        return cls(structured=validated, usage=usage or Usage())


class LLMProvider(ABC):
    """Abstract model provider. The only model seam agent logic may import."""

    name: str = "base"

    @abstractmethod
    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type[CoreContractModel] | None = None,
    ) -> LLMResponse:
        """Send ``messages`` at the given cost ``tier``.

        ``params``: provider-neutral generation parameters (e.g. ``temperature``, ``max_tokens``,
            ``top_p``). A generic dict only — never vendor-specific keys in agent logic.
        ``tools``: optional OpenAI-style tool schemas (provider-agnostic).
        ``response_schema``: optional deeply-immutable ``CoreContractModel`` class. **When provided,
            the implementation MUST validate output against it via
            ``LLMResponse.structured_from(response_schema, raw, usage=...)``** and return the
            validated instance in ``LLMResponse.structured`` (DESIGN §7 typed I/O). When omitted,
            return ``text`` (or a ``tool_call``).
        The returned ``LLMResponse`` carries exactly one payload and MUST report token/cost in
        ``LLMResponse.usage`` (provider-native), which feeds the one central cost ledger
        (``core.cost``).
        """
        raise NotImplementedError
