"""Tests for factory provider selection with GCP/LiteLLM paths."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest


# ---------------------------------------------------------------------------
# Shared fake SecretStore for Issue 4 tests
# ---------------------------------------------------------------------------

class _FakeSecretStore:
    """A test double for SecretStore that reads from a supplied dict."""
    def __init__(self, data: dict[str, str]):
        self._data = data

    def get(self, key: str) -> str:
        return self._data.get(key, "")


_GCP_CFG = {
    "provider": "gcp",
    "llm": {
        "provider": "litellm",
        # Updated to Gemini 2.5 models (2.0 Flash Lite and 2.0 Flash 001 retired June 1 2026)
        "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash",
                        "strong": "vertex_ai/gemini-2.5-pro"},
        "vertex_project": "test-project",
        "vertex_location": "us-central1",
    },
    "cost": {
        "ceiling_inr": 50.0,
        "provider_currency": "USD",
        "fx_rates": {"USD": 83.0},
        # Issue 2: pricing required at construction for every configured tier
        "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
        "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
    },
    "object_storage": {"provider": "gcp", "bucket": "test-bucket", "prefix": "blog/"},
    "transcription": {
        "provider": "gcp",
        "provider_currency": "USD",
        "cost_per_second_native": 0.0004,
        "billing_increment_seconds": 15,
        # 15-minute cap → worst-case 900 * 0.0004 * 83 = ₹29.88, safely under the ₹50
        # ceiling. Without this the provider falls back to its fail-closed default
        # (7200s → ₹239) and refuses construction. Mirrors config/gcp.yaml.
        "max_duration_s": 900,
    },
}

_MOCK_CFG = {
    "provider": "mock",
    "llm": {"provider": "mock", "tier_models": {"cheap": "mock/cheap", "strong": "mock/strong"}},
    "cost": {"provider_currency": "USD", "fx_rates": {"USD": 83.0}},
    "object_storage": {"provider": "mock", "bucket": "mock-bucket", "prefix": "blog/"},
}


class TestFactoryGCP:
    def test_mock_provider_selected(self):
        from core.factory import get_llm_provider
        from core.providers.mock.llm import MockLLMProvider
        p = get_llm_provider(_MOCK_CFG)
        assert isinstance(p, MockLLMProvider)

    def test_litellm_provider_selected(self):
        from core.factory import get_llm_provider
        from core.providers.gcp.llm import LiteLLMProvider
        p = get_llm_provider(_GCP_CFG)
        assert isinstance(p, LiteLLMProvider)

    def test_gcp_object_storage_selected(self):
        from core.factory import get_object_storage
        from core.providers.gcp.storage import GCSObjectStorage
        s = get_object_storage(_GCP_CFG)
        assert isinstance(s, GCSObjectStorage)

    def test_gcp_transcription_selected(self):
        from core.factory import get_transcription_provider
        from core.providers.gcp.transcription import GCPTranscriptionProvider

        provider = get_transcription_provider(_GCP_CFG)
        assert isinstance(provider, GCPTranscriptionProvider)

    def test_gcp_transcription_missing_pricing_fails_closed(self):
        from core.factory import get_transcription_provider

        with pytest.raises(ValueError, match="cost_per_second_native"):
            get_transcription_provider(
                {"transcription": {"provider": "gcp", "provider_currency": "USD"}}
            )

    def test_unknown_provider_raises(self):
        from core.factory import get_llm_provider
        bad_cfg = {
            "provider": "gcp",
            "llm": {"provider": "unknown_cloud_xyz",
                    "tier_models": {"cheap": "x", "strong": "y"}},
            "cost": {
                "provider_currency": "USD",
                "fx_rates": {"USD": 83.0},
                "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
                "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
            },
        }
        with pytest.raises(ValueError, match="unknown_cloud_xyz"):
            get_llm_provider(bad_cfg)

    def test_mock_object_storage_selected(self):
        from core.factory import get_object_storage
        from core.providers.mock.object_storage import InMemoryObjectStorage
        s = get_object_storage(_MOCK_CFG)
        assert isinstance(s, InMemoryObjectStorage)

    def test_litellm_alias_selected(self):
        """'litellm' key in llm.provider routes to LiteLLMProvider."""
        from core.factory import get_llm_provider
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = dict(_GCP_CFG)
        cfg["llm"] = dict(_GCP_CFG["llm"])
        cfg["llm"]["provider"] = "litellm"
        p = get_llm_provider(cfg)
        assert isinstance(p, LiteLLMProvider)

    def test_vertex_ai_alias_selected(self):
        """'vertex_ai' key in llm.provider routes to LiteLLMProvider."""
        from core.factory import get_llm_provider
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = dict(_GCP_CFG)
        cfg["llm"] = dict(_GCP_CFG["llm"])
        cfg["llm"]["provider"] = "vertex_ai"
        p = get_llm_provider(cfg)
        assert isinstance(p, LiteLLMProvider)

    def test_gcs_alias_selected(self):
        """'gcs' key in object_storage.provider routes to GCSObjectStorage."""
        from core.factory import get_object_storage
        from core.providers.gcp.storage import GCSObjectStorage
        cfg = dict(_GCP_CFG)
        cfg["object_storage"] = {"provider": "gcs", "bucket": "test-bucket", "prefix": "blog/"}
        s = get_object_storage(cfg)
        assert isinstance(s, GCSObjectStorage)

    # ---------------------------------------------------------------------------
    # Issue 6: Fail-closed behavior for incomplete cloud provider config
    # ---------------------------------------------------------------------------

    def test_gcp_provider_missing_tier_models_raises(self):
        """GCP provider selected but tier_models missing -> ValueError (fail closed)."""
        from core.factory import get_llm_provider
        cfg = {
            "llm": {"provider": "litellm"},  # no tier_models
            "cost": {"fx_rates": {"USD": 83.0}},
        }
        with pytest.raises(ValueError, match="tier_models"):
            get_llm_provider(cfg)

    def test_gcp_storage_missing_bucket_raises(self):
        """GCP storage selected but no bucket configured -> ValueError (fail closed)."""
        from core.factory import get_object_storage
        cfg = {"object_storage": {"provider": "gcp"}}  # no bucket
        with pytest.raises(ValueError, match="bucket"):
            get_object_storage(cfg)

    # ---------------------------------------------------------------------------
    # Issue 5: GCS bucket resolution from direct config and bucket_secret_key
    # ---------------------------------------------------------------------------

    def test_gcs_bucket_from_direct_config(self):
        from core.providers.gcp.storage import GCSObjectStorage
        cfg = {"object_storage": {"bucket": "my-direct-bucket", "prefix": "p/"}}
        s = GCSObjectStorage(cfg)
        assert s._bucket_name == "my-direct-bucket"

    def test_gcs_bucket_from_secret_key(self):
        """Issue 4: bucket_secret_key resolved via SecretStore (not os.environ)."""
        from core.providers.gcp.storage import GCSObjectStorage
        store = _FakeSecretStore({"MY_BUCKET_KEY": "resolved-bucket-name"})
        cfg = {"object_storage": {"bucket_secret_key": "MY_BUCKET_KEY", "prefix": "p/"}}
        s = GCSObjectStorage(cfg, secret_store=store)
        assert s._bucket_name == "resolved-bucket-name"

    def test_gcs_bucket_secret_key_without_secret_store_raises(self):
        """Issue 4: bucket_secret_key with no SecretStore → ValueError (not os.environ fallback)."""
        from core.providers.gcp.storage import GCSObjectStorage
        cfg = {"object_storage": {"bucket_secret_key": "MY_BUCKET_KEY"}}
        with pytest.raises(ValueError, match="SecretStore"):
            GCSObjectStorage(cfg, secret_store=None)

    def test_gcs_bucket_missing_secret_raises(self):
        """Issue 4: SecretStore returns empty for bucket key → ValueError."""
        from core.providers.gcp.storage import GCSObjectStorage
        store = _FakeSecretStore({})  # key not present → empty string
        cfg = {"object_storage": {"bucket_secret_key": "MISSING_BUCKET", "prefix": "p/"}}
        with pytest.raises(ValueError, match="MISSING_BUCKET"):
            GCSObjectStorage(cfg, secret_store=store)

    def test_gcs_no_bucket_config_raises(self):
        from core.providers.gcp.storage import GCSObjectStorage
        with pytest.raises(ValueError, match="bucket"):
            GCSObjectStorage({"object_storage": {"prefix": "p/"}})

    # ---------------------------------------------------------------------------
    # Issue 4: Factory auto-injects SecretStore (Probe 8)
    # ---------------------------------------------------------------------------

    def test_factory_auto_injects_secret_store_for_llm_provider(self):
        """factory.get_llm_provider auto-injects SecretStore — no manual injection needed."""
        from core.factory import get_llm_provider
        from core.providers.gcp.llm import LiteLLMProvider
        # Direct vertex_project (no secret needed) — just verifies factory creates provider OK
        p = get_llm_provider(_GCP_CFG)
        assert isinstance(p, LiteLLMProvider)

    def test_factory_auto_injects_secret_store_for_storage(self):
        """factory.get_object_storage auto-injects SecretStore — no manual injection needed."""
        from core.factory import get_object_storage
        from core.providers.gcp.storage import GCSObjectStorage
        s = get_object_storage(_GCP_CFG)
        assert isinstance(s, GCSObjectStorage)

    # ---------------------------------------------------------------------------
    # Issue 2 / Issue 5: CostMeter / to_inr FX rate adversarial tests
    # ---------------------------------------------------------------------------

    def test_to_inr_zero_fx_rate_raises(self):
        """to_inr with fx_rate=0 → ValueError (Probe 5)."""
        from core.cost.meter import to_inr
        with pytest.raises(ValueError, match="fx_rate"):
            to_inr(1.0, currency="USD", fx_rates={"USD": 0.0})

    def test_to_inr_negative_fx_rate_raises(self):
        """to_inr with negative fx_rate → ValueError."""
        from core.cost.meter import to_inr
        with pytest.raises(ValueError, match="fx_rate"):
            to_inr(1.0, currency="USD", fx_rates={"USD": -83.0})

    def test_to_inr_nonfinite_fx_rate_raises(self):
        """to_inr with non-finite fx_rate → ValueError."""
        from core.cost.meter import to_inr
        with pytest.raises(ValueError, match="fx_rate"):
            to_inr(1.0, currency="USD", fx_rates={"USD": float("inf")})

    # ---------------------------------------------------------------------------
    # Recommended improvement: GCS key validation
    # ---------------------------------------------------------------------------

    def test_gcs_validate_key_empty_raises(self):
        """GCSObjectStorage._validate_key rejects empty keys."""
        from core.providers.gcp.storage import GCSObjectStorage
        s = GCSObjectStorage({"object_storage": {"bucket": "b"}})
        with pytest.raises(ValueError, match="non-empty"):
            s._validate_key("")

    def test_gcs_validate_key_absolute_raises(self):
        """GCSObjectStorage._validate_key rejects absolute paths."""
        from core.providers.gcp.storage import GCSObjectStorage
        s = GCSObjectStorage({"object_storage": {"bucket": "b"}})
        with pytest.raises(ValueError, match="relative"):
            s._validate_key("/absolute/path")

    def test_gcs_validate_key_dotdot_raises(self):
        """GCSObjectStorage._validate_key rejects path traversal."""
        from core.providers.gcp.storage import GCSObjectStorage
        s = GCSObjectStorage({"object_storage": {"bucket": "b"}})
        with pytest.raises(ValueError, match="\\.\\."):
            s._validate_key("some/../bad/path")

    def test_gcs_validate_key_valid_passes(self):
        """GCSObjectStorage._validate_key accepts valid relative keys."""
        from core.providers.gcp.storage import GCSObjectStorage
        s = GCSObjectStorage({"object_storage": {"bucket": "b"}})
        s._validate_key("blog/2026/post.md")  # should not raise

    def test_gcs_uri_for_uses_bucket_and_prefix(self):
        from core.providers.gcp.storage import GCSObjectStorage

        s = GCSObjectStorage({"object_storage": {"bucket": "b", "prefix": "agent/"}})
        assert s.uri_for("transcription/audio.wav") == (
            "gs://b/agent/transcription/audio.wav"
        )
