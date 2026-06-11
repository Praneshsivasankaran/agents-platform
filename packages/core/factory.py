"""Provider factory — the SINGLE config-driven selection point (DESIGN §4.2).

Each ``get_*`` maps config (``provider = mock | litellm | gcp | bedrock | azure``) to a concrete
implementation of the matching interface. This is the only place the platform resolves a backend;
agent logic calls these, never a cloud SDK.

Current state (Increment 7):
- ``mock`` / ``offline``: MockLLMProvider, InMemoryObjectStorage — offline CI only, no credentials.
- ``litellm`` / ``gcp`` / ``vertex`` / ``vertex_ai``: LiteLLMProvider (Vertex AI via LiteLLM),
  GCSObjectStorage (google-cloud-storage) — auto-injects EnvSecretStore for credential resolution.
- ``transcription.provider = gcp``: priced, bounded GCPTranscriptionProvider.
- ``bedrock`` / ``aws`` / ``azure``: interface-complete stubs. The factory **constructs and returns
  the stub instance** (it satisfies the ABC and is indistinguishable from a wired backend at
  construction); the stub's methods raise a loud ``NotImplementedError`` when called. This makes
  config-only swap testable today and "going live" a body-fill + config flip, not a redesign.

``secret_store`` / ``telemetry`` are cloud-agnostic (env / stdout / OTel) and are NOT cloud-variant
stubs; requesting ``secret_store.provider`` in ``_NOT_WIRED`` (a cloud secret manager) still raises.
SecretStore is auto-injected by the factory so callers do not need to inject it manually.
"""

from __future__ import annotations

from typing import Any, Callable

from .interfaces import (
    LLMProvider,
    ObjectStorage,
    SecretStore,
    Telemetry,
    TranscriptionProvider,
)

_NOT_WIRED = ("bedrock", "aws", "azure")


def _section(cfg: dict[str, Any], key: str) -> dict[str, Any]:
    section = cfg.get(key) or {}
    return section if isinstance(section, dict) else {}


def _provided_or(kwargs: dict[str, Any], key: str, default_factory: Callable[[], Any]) -> Any:
    """Preserve any explicitly supplied non-None dependency, including falsey test doubles."""
    value = kwargs.get(key)
    return default_factory() if value is None else value


def get_llm_provider(cfg: dict[str, Any], **kwargs) -> LLMProvider:
    # Determine the provider key
    llm_cfg = _section(cfg, "llm")
    provider_key = llm_cfg.get("provider") or cfg.get("provider", "mock")

    if provider_key in ("mock", "offline", ""):
        from .providers.mock import MockLLMProvider

        scenario = llm_cfg.get("mock_scenario", "pass")
        return MockLLMProvider(default_scenario=scenario)

    if provider_key in ("litellm", "gcp", "vertex", "vertex_ai"):
        # Issue 6: Fail closed — tier_models must be present for cloud providers
        tier_models = llm_cfg.get("tier_models", {})
        if not tier_models:
            raise ValueError(
                f"LLM provider={provider_key!r} selected but cfg.llm.tier_models "
                f"is missing or empty — cannot route to cloud without model mappings"
            )
        from .providers.gcp.llm import LiteLLMProvider

        # Issue 4 Fix A: Auto-inject SecretStore when caller does not provide one.
        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return LiteLLMProvider(cfg, secret_store=secret_store)

    if provider_key in ("bedrock", "aws"):
        # Interface-complete stub: instantiable, satisfies the ABC, raises loudly on respond().
        # Auto-inject SecretStore (same as the GCP path) so config-only swap is genuinely
        # dependency-complete — a future fill-in resolves creds without caller changes.
        from .providers.bedrock.llm import BedrockLLMProvider

        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return BedrockLLMProvider(cfg, secret_store=secret_store)

    if provider_key == "azure":
        from .providers.azure.llm import AzureLLMProvider

        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return AzureLLMProvider(cfg, secret_store=secret_store)

    raise ValueError(
        f"Unknown LLM provider {provider_key!r}. "
        f"Supported: mock, litellm, gcp, vertex, vertex_ai, bedrock, aws, azure"
    )


def get_transcription_provider(cfg: dict[str, Any], **kwargs) -> TranscriptionProvider:
    provider = _section(cfg, "transcription").get("provider", "mock")
    if provider in ("mock", "offline"):
        from .providers.mock import MockTranscriptionProvider

        return MockTranscriptionProvider()
    if provider in ("gcp", "google", "gcp_speech"):
        from .providers.gcp.transcription import GCPTranscriptionProvider

        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return GCPTranscriptionProvider(
            cfg,
            secret_store=secret_store,
            object_storage=kwargs.get("object_storage"),
        )
    if provider in ("bedrock", "aws"):
        from .providers.bedrock.transcription import BedrockTranscriptionProvider

        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return BedrockTranscriptionProvider(
            cfg,
            secret_store=secret_store,
            object_storage=_provided_or(kwargs, "object_storage", lambda: get_object_storage(cfg)),
        )
    if provider == "azure":
        from .providers.azure.transcription import AzureTranscriptionProvider

        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return AzureTranscriptionProvider(
            cfg,
            secret_store=secret_store,
            object_storage=_provided_or(kwargs, "object_storage", lambda: get_object_storage(cfg)),
        )
    if provider == "whisper":
        raise NotImplementedError("transcription provider 'whisper' is a v1 placeholder (not wired yet)")
    raise ValueError(f"unknown transcription.provider: {provider!r}")


def get_object_storage(cfg: dict[str, Any], **kwargs) -> ObjectStorage:
    storage_cfg = _section(cfg, "object_storage")
    provider_key = storage_cfg.get("provider", cfg.get("provider", "mock"))

    if provider_key in ("memory", "mock", "offline", ""):
        from .providers.mock import InMemoryObjectStorage

        return InMemoryObjectStorage()

    if provider_key in ("gcp", "gcs", "google"):
        # Issue 6: Fail closed — bucket config must be present for cloud storage
        bucket = storage_cfg.get("bucket", "") or storage_cfg.get("bucket_secret_key", "")
        if not bucket:
            raise ValueError(
                f"Object storage provider={provider_key!r} selected but neither "
                f"cfg.object_storage.bucket nor cfg.object_storage.bucket_secret_key "
                f"is configured"
            )
        from .providers.gcp.storage import GCSObjectStorage

        # Issue 4 Fix A: Auto-inject SecretStore when caller does not provide one.
        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return GCSObjectStorage(cfg, secret_store=secret_store)

    if provider_key in ("bedrock", "aws", "s3"):
        from .providers.bedrock.storage import BedrockObjectStorage

        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return BedrockObjectStorage(cfg, secret_store=secret_store)

    if provider_key in ("azure", "azure_blob"):
        from .providers.azure.storage import AzureObjectStorage

        secret_store = _provided_or(kwargs, "secret_store", lambda: get_secret_store(cfg))
        return AzureObjectStorage(cfg, secret_store=secret_store)

    raise ValueError(
        f"Unknown object storage provider {provider_key!r}. "
        f"Supported: mock, memory, gcp, gcs, google, bedrock, aws, s3, azure, azure_blob"
    )


def get_secret_store(cfg: dict[str, Any]) -> SecretStore:
    provider = _section(cfg, "secret_store").get("provider", "env")
    if provider in ("env", "mock", "offline"):
        from .providers.mock import EnvSecretStore

        return EnvSecretStore()
    if provider in _NOT_WIRED:
        raise NotImplementedError(f"secret_store provider '{provider}' is a v1 placeholder (not wired yet)")
    raise ValueError(f"unknown secret_store.provider: {provider!r}")


def get_telemetry(cfg: dict[str, Any]) -> Telemetry:
    tcfg = _section(cfg, "telemetry")
    provider = tcfg.get("provider", "stdout")
    if provider in ("stdout", "mock", "offline"):
        from .providers.mock import StdoutTelemetry

        # Per-agent event codes: telemetry.extra_labels: [ "intake.complete", ... ]
        raw_labels = tcfg.get("extra_labels")
        extra_labels = (
            frozenset(str(x) for x in raw_labels)
            if isinstance(raw_labels, (list, tuple, set, frozenset))
            else None
        )
        # Per-agent dimension enums: telemetry.dimensions: { node: [ "intake", ... ], ... }
        # Dimensions are finite enums (list-valued); there are no regex-authorized dimensions.
        raw_dims = tcfg.get("dimensions")
        dimensions = None
        if isinstance(raw_dims, dict):
            dimensions = {
                str(k): frozenset(str(v) for v in vals)
                for k, vals in raw_dims.items()
                if isinstance(vals, (list, tuple, set, frozenset))
            } or None
        # Per-agent registered attribute keys: telemetry.attr_keys: [ "stage_count", ... ]
        raw_attr_keys = tcfg.get("attr_keys")
        attr_keys = (
            frozenset(str(x) for x in raw_attr_keys)
            if isinstance(raw_attr_keys, (list, tuple, set, frozenset))
            else None
        )
        # Per-agent registered metric names: telemetry.extra_metric_names: [ "agent.total_cost_inr", ... ]
        # Only names in this set (∪ _PLATFORM_METRIC_NAMES) may carry raw numeric values through metric().
        raw_metric_names = tcfg.get("extra_metric_names")
        extra_metric_names = (
            frozenset(str(x) for x in raw_metric_names)
            if isinstance(raw_metric_names, (list, tuple, set, frozenset))
            else None
        )
        return StdoutTelemetry(
            service=cfg.get("service", "agents-platform"),
            extra_labels=extra_labels,
            dimensions=dimensions,
            attr_keys=attr_keys,
            extra_metric_names=extra_metric_names,
        )
    if provider in ("otel", "opentelemetry"):
        raise NotImplementedError("telemetry provider 'otel' is a v1 placeholder (not wired yet)")
    raise ValueError(f"unknown telemetry.provider: {provider!r}")
