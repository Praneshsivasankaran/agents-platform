"""Interface-level tests for the Bedrock + Azure provider stubs (Increment 7).

Per DESIGN §4.2/§12 and plan §8: each stub must (a) satisfy its interface ABC, (b) be
instantiable like a wired backend, and (c) fail **loudly** (NotImplementedError) on every
unfilled method — never silently pass. The factory must select them by config with no agent
change, and importing/constructing them must NOT pull in any cloud SDK (offline-safe).
"""
from __future__ import annotations

import sys

import pytest

from core.interfaces.llm import LLMProvider
from core.interfaces.object_storage import ObjectStorage
from core.interfaces.transcription import TranscriptionProvider

from core.providers.bedrock.llm import BedrockLLMProvider
from core.providers.bedrock.transcription import BedrockTranscriptionProvider
from core.providers.bedrock.storage import BedrockObjectStorage
from core.providers.azure.llm import AzureLLMProvider
from core.providers.azure.transcription import AzureTranscriptionProvider
from core.providers.azure.storage import AzureObjectStorage


_LLM_STUBS = [BedrockLLMProvider, AzureLLMProvider]
_STT_STUBS = [BedrockTranscriptionProvider, AzureTranscriptionProvider]
_STORAGE_STUBS = [BedrockObjectStorage, AzureObjectStorage]
_ALL_STUBS = _LLM_STUBS + _STT_STUBS + _STORAGE_STUBS


# ---------------------------------------------------------------------------
# ABC satisfaction + instantiability
# ---------------------------------------------------------------------------

class TestStubInterfaceCompleteness:
    @pytest.mark.parametrize("cls", _LLM_STUBS)
    def test_llm_is_llmprovider(self, cls):
        assert issubclass(cls, LLMProvider)
        assert isinstance(cls({}), LLMProvider)

    @pytest.mark.parametrize("cls", _STT_STUBS)
    def test_stt_is_transcriptionprovider(self, cls):
        assert issubclass(cls, TranscriptionProvider)
        assert isinstance(cls({}), TranscriptionProvider)

    @pytest.mark.parametrize("cls", _STORAGE_STUBS)
    def test_storage_is_objectstorage(self, cls):
        assert issubclass(cls, ObjectStorage)
        assert isinstance(cls({}), ObjectStorage)

    @pytest.mark.parametrize("cls", _ALL_STUBS)
    def test_constructor_does_not_raise(self, cls):
        # Instantiable with no cfg, empty cfg, and factory-style kwargs.
        cls()
        cls({})
        cls({"anything": 1}, secret_store=object())

    @pytest.mark.parametrize("cls", _ALL_STUBS)
    def test_has_name(self, cls):
        assert isinstance(cls().name, str) and cls().name


# ---------------------------------------------------------------------------
# Loud failure on every method
# ---------------------------------------------------------------------------

class TestStubsFailLoudly:
    @pytest.mark.parametrize("cls", _LLM_STUBS)
    def test_respond_raises(self, cls):
        with pytest.raises(NotImplementedError):
            cls({}).respond([{"role": "user", "content": "hi"}], tier="cheap")

    @pytest.mark.parametrize("cls", _STT_STUBS)
    def test_transcribe_raises(self, cls):
        with pytest.raises(NotImplementedError):
            cls({}).transcribe("audio.wav")

    @pytest.mark.parametrize("cls", _STORAGE_STUBS)
    def test_storage_methods_raise(self, cls):
        s = cls({})
        with pytest.raises(NotImplementedError):
            s.put("k", b"data")
        with pytest.raises(NotImplementedError):
            s.get("k")
        with pytest.raises(NotImplementedError):
            s.delete("k")

    def test_error_message_is_descriptive_not_silent(self):
        """A loud failure names the cloud + method, so it can't be mistaken for a pass."""
        with pytest.raises(NotImplementedError, match="AWS Bedrock LLM"):
            BedrockLLMProvider({}).respond([], tier="strong")
        with pytest.raises(NotImplementedError, match="Azure AI Speech"):
            AzureTranscriptionProvider({}).transcribe("a.wav")
        with pytest.raises(NotImplementedError, match="S3"):
            BedrockObjectStorage({}).get("k")
        with pytest.raises(NotImplementedError, match="not wired"):
            AzureObjectStorage({}).put("k", b"x")


# ---------------------------------------------------------------------------
# Factory selection (config → stub class) — config-only swap, no agent change
# ---------------------------------------------------------------------------

def _llm_cfg(provider):
    return {"llm": {"provider": provider, "tier_models": {"cheap": "x", "strong": "y"}}}


class TestFactorySelectsStubs:
    @pytest.mark.parametrize("provider", ["bedrock", "aws"])
    def test_llm_bedrock(self, provider):
        from core.factory import get_llm_provider
        assert isinstance(get_llm_provider(_llm_cfg(provider)), BedrockLLMProvider)

    def test_llm_azure(self):
        from core.factory import get_llm_provider
        assert isinstance(get_llm_provider(_llm_cfg("azure")), AzureLLMProvider)

    @pytest.mark.parametrize("provider", ["bedrock", "aws"])
    def test_transcription_bedrock(self, provider):
        from core.factory import get_transcription_provider
        cfg = {"transcription": {"provider": provider}}
        assert isinstance(get_transcription_provider(cfg), BedrockTranscriptionProvider)

    def test_transcription_azure(self):
        from core.factory import get_transcription_provider
        cfg = {"transcription": {"provider": "azure"}}
        assert isinstance(get_transcription_provider(cfg), AzureTranscriptionProvider)

    @pytest.mark.parametrize("provider", ["bedrock", "aws", "s3"])
    def test_storage_bedrock(self, provider):
        from core.factory import get_object_storage
        cfg = {"object_storage": {"provider": provider}}
        assert isinstance(get_object_storage(cfg), BedrockObjectStorage)

    @pytest.mark.parametrize("provider", ["azure", "azure_blob"])
    def test_storage_azure(self, provider):
        from core.factory import get_object_storage
        cfg = {"object_storage": {"provider": provider}}
        assert isinstance(get_object_storage(cfg), AzureObjectStorage)

    def test_selected_stub_still_fails_loudly(self):
        """End-to-end: factory returns a stub, and calling through it raises loudly."""
        from core.factory import get_llm_provider, get_transcription_provider
        with pytest.raises(NotImplementedError):
            get_llm_provider(_llm_cfg("bedrock")).respond([], tier="cheap")
        with pytest.raises(NotImplementedError):
            get_transcription_provider({"transcription": {"provider": "azure"}}).transcribe("a.wav")


# ---------------------------------------------------------------------------
# Offline-safety: no cloud SDK imported by constructing/selecting a stub
# ---------------------------------------------------------------------------

class TestStubsImportNoCloudSDK:
    def test_no_aws_or_azure_sdk_loaded(self):
        from core.factory import get_llm_provider, get_object_storage, get_transcription_provider

        get_llm_provider(_llm_cfg("bedrock")).__class__  # construct
        get_llm_provider(_llm_cfg("azure"))
        get_transcription_provider({"transcription": {"provider": "bedrock"}})
        get_transcription_provider({"transcription": {"provider": "azure"}})
        get_object_storage({"object_storage": {"provider": "s3"}})
        get_object_storage({"object_storage": {"provider": "azure"}})

        for banned in ("boto3", "botocore", "amazon_transcribe", "azure"):
            assert banned not in sys.modules, (
                f"{banned!r} was imported by a stub — stubs must defer cloud SDK imports "
                f"until a method body is filled in"
            )


# ---------------------------------------------------------------------------
# Factory auto-injects dependencies (config-only swap must be dependency-complete)
# ---------------------------------------------------------------------------

class TestFactoryInjectsDependencies:
    @pytest.mark.parametrize("provider,cls", [("bedrock", BedrockLLMProvider), ("azure", AzureLLMProvider)])
    def test_llm_stub_receives_secret_store(self, provider, cls):
        from core.factory import get_llm_provider
        stub = get_llm_provider(_llm_cfg(provider))
        assert isinstance(stub, cls)
        assert stub._secret_store is not None  # factory auto-injected EnvSecretStore

    @pytest.mark.parametrize("provider", ["bedrock", "azure"])
    def test_transcription_stub_receives_secret_store_and_object_storage(self, provider):
        from core.factory import get_transcription_provider
        stub = get_transcription_provider({"transcription": {"provider": provider}})
        assert stub._secret_store is not None
        assert stub._object_storage is not None  # injected configured/stub object storage

    @pytest.mark.parametrize("provider,cls", [("bedrock", BedrockObjectStorage), ("azure", AzureObjectStorage)])
    def test_storage_stub_receives_secret_store(self, provider, cls):
        from core.factory import get_object_storage
        stub = get_object_storage({"object_storage": {"provider": provider}})
        assert isinstance(stub, cls)
        assert stub._secret_store is not None

    def test_explicitly_supplied_dependencies_are_preserved(self):
        """A caller-supplied SecretStore/ObjectStorage must NOT be overridden by auto-injection."""
        from core.factory import get_llm_provider, get_object_storage, get_transcription_provider
        sentinel_secret = object()
        sentinel_storage = object()
        assert get_llm_provider(_llm_cfg("bedrock"), secret_store=sentinel_secret)._secret_store is sentinel_secret
        assert get_object_storage({"object_storage": {"provider": "azure"}},
                                  secret_store=sentinel_secret)._secret_store is sentinel_secret
        t = get_transcription_provider({"transcription": {"provider": "bedrock"}},
                                       secret_store=sentinel_secret, object_storage=sentinel_storage)
        assert t._secret_store is sentinel_secret
        assert t._object_storage is sentinel_storage

    def test_falsey_explicit_dependencies_are_preserved(self):
        """Dependency injection must use an explicit None check, not truthiness."""
        from core.factory import get_llm_provider, get_object_storage, get_transcription_provider

        class FalseyDependency:
            def __bool__(self):
                return False

        sentinel_secret = FalseyDependency()
        sentinel_storage = FalseyDependency()
        assert (
            get_llm_provider(_llm_cfg("azure"), secret_store=sentinel_secret)._secret_store
            is sentinel_secret
        )
        assert (
            get_object_storage(
                {"object_storage": {"provider": "bedrock"}},
                secret_store=sentinel_secret,
            )._secret_store
            is sentinel_secret
        )
        transcription = get_transcription_provider(
            {"transcription": {"provider": "azure"}},
            secret_store=sentinel_secret,
            object_storage=sentinel_storage,
        )
        assert transcription._secret_store is sentinel_secret
        assert transcription._object_storage is sentinel_storage
