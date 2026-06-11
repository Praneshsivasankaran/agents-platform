"""Config-only swap demo for the Bedrock/Azure overlays (Increment 7).

Proves the platform's central claim (DESIGN §4.2, plan §8): selecting a different cloud is a
config change only. Loading base.yaml + {bedrock,azure}.yaml and handing the merged dict to the
factory selects that cloud's stub providers across all three data-plane seams — with no agent
code change. The stubs are interface-complete, so the agent could not tell them from a wired
backend until a call is actually made (which then fails loudly).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.factory import get_llm_provider, get_object_storage, get_transcription_provider
from core.providers.azure.llm import AzureLLMProvider
from core.providers.azure.storage import AzureObjectStorage
from core.providers.azure.transcription import AzureTranscriptionProvider
from core.providers.bedrock.llm import BedrockLLMProvider
from core.providers.bedrock.storage import BedrockObjectStorage
from core.providers.bedrock.transcription import BedrockTranscriptionProvider

_CONFIG_DIR = Path(__file__).parents[2] / "config"


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _merged(overlay_name: str) -> dict:
    base = yaml.safe_load((_CONFIG_DIR / "base.yaml").read_text(encoding="utf-8"))
    overlay = yaml.safe_load((_CONFIG_DIR / overlay_name).read_text(encoding="utf-8"))
    return _deep_merge(base, overlay)


class TestBedrockOverlay:
    def test_overlay_file_exists_and_selects_bedrock(self):
        merged = _merged("bedrock.yaml")
        assert merged["provider"] == "bedrock"
        assert merged["llm"]["provider"] == "bedrock"
        assert merged["transcription"]["provider"] == "bedrock"
        assert merged["object_storage"]["provider"] == "bedrock"
        # Cloud-agnostic seams stay env/stdout.
        assert merged["secret_store"]["provider"] == "env"
        assert merged["telemetry"]["provider"] == "stdout"

    def test_factory_selects_bedrock_stubs_across_all_seams(self):
        merged = _merged("bedrock.yaml")
        assert isinstance(get_llm_provider(merged), BedrockLLMProvider)
        assert isinstance(get_transcription_provider(merged), BedrockTranscriptionProvider)
        assert isinstance(get_object_storage(merged), BedrockObjectStorage)

    def test_selected_bedrock_llm_fails_loudly(self):
        provider = get_llm_provider(_merged("bedrock.yaml"))
        with pytest.raises(NotImplementedError):
            provider.respond([{"role": "user", "content": "hi"}], tier="cheap")


class TestAzureOverlay:
    def test_overlay_file_exists_and_selects_azure(self):
        merged = _merged("azure.yaml")
        assert merged["provider"] == "azure"
        assert merged["llm"]["provider"] == "azure"
        assert merged["transcription"]["provider"] == "azure"
        assert merged["object_storage"]["provider"] == "azure"
        assert merged["secret_store"]["provider"] == "env"
        assert merged["telemetry"]["provider"] == "stdout"

    def test_factory_selects_azure_stubs_across_all_seams(self):
        merged = _merged("azure.yaml")
        assert isinstance(get_llm_provider(merged), AzureLLMProvider)
        assert isinstance(get_transcription_provider(merged), AzureTranscriptionProvider)
        assert isinstance(get_object_storage(merged), AzureObjectStorage)

    def test_selected_azure_transcription_fails_loudly(self):
        provider = get_transcription_provider(_merged("azure.yaml"))
        with pytest.raises(NotImplementedError):
            provider.transcribe("recording.wav")


class TestOverlayShapeMatchesGcp:
    """The stub overlays must carry the same config shape as the real gcp.yaml, so swapping
    is purely a value change (no missing/extra keys that agent code would trip on)."""

    @pytest.mark.parametrize("overlay", ["bedrock.yaml", "azure.yaml"])
    def test_required_sections_present(self, overlay):
        merged = _merged(overlay)
        for section in ("llm", "cost", "object_storage", "transcription"):
            assert section in merged
        assert "tier_models" in merged["llm"]
        assert merged["cost"]["ceiling_inr"] == 50.0
        assert "fx_rates" in merged["cost"]
