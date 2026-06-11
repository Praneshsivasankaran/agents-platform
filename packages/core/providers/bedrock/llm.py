"""Amazon Bedrock LLM provider — interface-complete stub (v1; not wired).

Satisfies the ``LLMProvider`` ABC. ``respond`` raises ``NotImplementedError`` loudly. When this
is filled in, boto3 (``bedrock-runtime``) will be imported lazily here — never in agent logic.
"""

from __future__ import annotations

from typing import Any

from ...interfaces.base import CoreContractModel
from ...interfaces.llm import LLMProvider, LLMResponse, Tier
from .._not_wired import not_wired


class BedrockLLMProvider(LLMProvider):
    """AWS Bedrock model backend (stub). Instantiable; ``respond`` fails loudly."""

    name = "bedrock"

    def __init__(self, cfg: dict[str, Any] | None = None, *, secret_store=None, **_: Any) -> None:
        # Stored for the real implementation; no validation here so the stub is instantiable
        # and the factory can construct it uniformly (DESIGN §4.2).
        self._cfg = cfg or {}
        self._secret_store = secret_store

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type[CoreContractModel] | None = None,
    ) -> LLMResponse:
        raise not_wired("AWS", "Bedrock LLM", "respond")
