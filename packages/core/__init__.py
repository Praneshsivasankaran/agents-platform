"""packages/core — shared, cloud-neutral provider abstractions + utilities.

Every agent imports its provider seams from here and NOTHING cloud-specific. The
``agents/*/agent/`` layer must never import ``google.cloud`` / ``vertexai`` / ``boto3``
/ ``botocore`` / ``azure`` or any STT SDK — enforced in CI by ``core.checks.no_cloud_sdk``
(DESIGN §4, §12; scoped to ``agents/*/agent/``; auto-discovers all agent dirs; fail-closed).

Current state: GCP/Vertex LiteLLM provider (``core.providers.gcp.llm``), GCS object storage,
BillableProviderError with pickle-safe sanitized cause, provider factory with SecretStore
injection (``core.factory``), cost meter with INR ceiling enforcement, and offline mock
providers for CI. Agent logic (agent-01-blog-writer) is implemented and tested offline.
"""

from __future__ import annotations

from .interfaces import (
    BillableProviderError,
    CoreContractModel,
    LLMProvider,
    LLMResponse,
    ObjectStorage,
    SecretStore,
    Telemetry,
    Tier,
    TimestampSegment,
    ToolCall,
    Transcript,
    TranscriptionProvider,
    Usage,
    validate_structured_schema,
)

__all__ = [
    "BillableProviderError",
    "CoreContractModel",
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "Usage",
    "Tier",
    "TranscriptionProvider",
    "Transcript",
    "TimestampSegment",
    "ObjectStorage",
    "SecretStore",
    "Telemetry",
    "validate_structured_schema",
]
