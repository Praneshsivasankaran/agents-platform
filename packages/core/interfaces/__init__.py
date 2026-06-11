"""Cloud-neutral provider interfaces (ABCs + typed Pydantic contracts).

These are the only seams ``agents/*/agent/`` logic may import. Modules import only Pydantic +
the standard library — never a cloud SDK. Concrete implementations live under ``core.providers``
and are selected by config via ``core.factory`` (later increment).
"""

from __future__ import annotations

from .base import CoreContractModel, validate_structured_schema
from .errors import BillableProviderError
from .llm import LLMProvider, LLMResponse, Tier, ToolCall
from .object_storage import ObjectStorage
from .secret_store import SecretStore
from .telemetry import Telemetry
from .transcription import TimestampSegment, Transcript, TranscriptionProvider
from .usage import Usage

__all__ = [
    "BillableProviderError",
    "CoreContractModel",
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "Tier",
    "Usage",
    "TranscriptionProvider",
    "Transcript",
    "TimestampSegment",
    "ObjectStorage",
    "SecretStore",
    "Telemetry",
    "validate_structured_schema",
]
