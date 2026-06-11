"""Azure OpenAI LLM provider — interface-complete stub (v1; not wired).

Satisfies the ``LLMProvider`` ABC. ``respond`` raises ``NotImplementedError`` loudly. When
filled in, the Azure OpenAI client is imported lazily here — never in agent logic.
"""

from __future__ import annotations

from typing import Any

from ...interfaces.base import CoreContractModel
from ...interfaces.llm import LLMProvider, LLMResponse, Tier
from .._not_wired import not_wired


class AzureLLMProvider(LLMProvider):
    """Azure OpenAI model backend (stub). Instantiable; ``respond`` fails loudly."""

    name = "azure"

    def __init__(self, cfg: dict[str, Any] | None = None, *, secret_store=None, **_: Any) -> None:
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
        raise not_wired("Azure", "OpenAI LLM", "respond")
