"""Live GCP/Vertex smoke test — merge gate, not offline CI.

This file has NO skip guards. The offline CI job (core-offline) excludes tests/smoke/
entirely by path omission — it never runs these files. The live-smoke CI job sets real
credentials via google-github-actions/auth and the VERTEX_AI_PROJECT secret,
so tests always run there.

pytestmark = pytest.mark.smoke labels all tests for selective execution.
The live-smoke CI job runs: pytest tests/smoke -x (stop at first failure).
"""
from __future__ import annotations
import math
from pathlib import Path
import tempfile
import wave
import pytest

pytestmark = [pytest.mark.smoke]

_SMOKE_COST_CAP_INR = 10.0  # strict per-run cap for smoke tests


def _load_gcp_cfg() -> dict:
    """Load base.yaml deep-merged with gcp.yaml."""
    import yaml
    base_path = Path(__file__).parent.parent.parent / "config" / "base.yaml"
    gcp_path = Path(__file__).parent.parent.parent / "config" / "gcp.yaml"

    base = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    gcp = yaml.safe_load(gcp_path.read_text(encoding="utf-8"))

    def deep_merge(a: dict, b: dict) -> dict:
        result = dict(a)
        for k, v in b.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    return deep_merge(base, gcp)


@pytest.fixture(scope="module")
def _cfg():
    return _load_gcp_cfg()


def _make_llm_provider(_cfg):
    """Build LiteLLMProvider with factory-injected EnvSecretStore.

    Direct construction of LiteLLMProvider without a SecretStore would raise
    when vertex_project_secret is configured (Issue 4 enforcement). The factory
    auto-injects EnvSecretStore so VERTEX_AI_PROJECT is resolved at runtime.
    """
    from core.factory import get_llm_provider
    return get_llm_provider(_cfg)


def test_smoke_vertex_config_forwarded(_cfg):
    """Provider forwards exact configured model IDs, project, and location."""
    import yaml
    import pathlib

    cfg_path = pathlib.Path(__file__).parent.parent.parent / "config" / "gcp.yaml"
    with open(cfg_path) as f:
        raw_cfg = yaml.safe_load(f)

    provider = _make_llm_provider(_cfg)

    expected_cheap = raw_cfg["llm"]["tier_models"]["cheap"]
    expected_strong = raw_cfg["llm"]["tier_models"]["strong"]

    # Model IDs match config exactly — no substring assertion
    assert provider._tier_models["cheap"] == expected_cheap, (
        f"cheap model {provider._tier_models['cheap']!r} != config {expected_cheap!r}"
    )
    assert provider._tier_models["strong"] == expected_strong, (
        f"strong model {provider._tier_models['strong']!r} != config {expected_strong!r}"
    )

    # Project and location are set
    assert provider._vertex_project, (
        "vertex_project is empty — set VERTEX_AI_PROJECT env var "
        "and configure llm.vertex_project_secret in gcp.yaml"
    )
    assert provider._vertex_location, "vertex_location must be set"


def test_smoke_gcp_transcription_configured(_cfg):
    """The GCP overlay must select the real, cost-accounted STT provider."""
    from core.factory import get_transcription_provider
    from core.providers.gcp.transcription import GCPTranscriptionProvider

    provider = get_transcription_provider(_cfg)
    assert isinstance(provider, GCPTranscriptionProvider)
    assert provider._cost_per_second_native > 0
    assert provider._currency == "USD"


def test_smoke_gcp_transcription_live_call(_cfg):
    """Exercise the real Speech API with one second of silence.

    A successful API response contains no transcript, so the provider deliberately
    raises ``response_empty`` after the billable call. Permission/network failures
    produce ``provider_call_failed`` and therefore fail this smoke test.
    """
    from core.factory import get_transcription_provider
    from core.interfaces import BillableProviderError

    provider = get_transcription_provider(_cfg)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        audio_path = fh.name
    try:
        with wave.open(audio_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * 16000)
        with pytest.raises(BillableProviderError) as exc_info:
            provider.transcribe(audio_path)
        assert exc_info.value.category == "response_empty"
        assert exc_info.value.usage.cost_native > 0
        assert exc_info.value.usage.currency == "USD"
    finally:
        Path(audio_path).unlink(missing_ok=True)


def test_smoke_gcp_long_form_transcription_live_call(_cfg):
    """Exercise long-running Speech recognition through transient GCS storage.

    The 56-second silent WAV is just above the configured synchronous threshold.
    A successful call must reach the provider and then fail only with
    ``response_empty`` after the transient GCS object has been deleted.
    """
    from core.factory import get_transcription_provider
    from core.interfaces import BillableProviderError

    provider = get_transcription_provider(_cfg)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        audio_path = fh.name
    try:
        with wave.open(audio_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * (16000 * 56))
        with pytest.raises(BillableProviderError) as exc_info:
            provider.transcribe(audio_path)
        assert exc_info.value.category == "response_empty"
        assert exc_info.value.usage.audio_seconds == pytest.approx(56.0)
        assert exc_info.value.usage.cost_native > 0
        assert exc_info.value.usage.currency == "USD"
    finally:
        Path(audio_path).unlink(missing_ok=True)


def test_smoke_text_response(_cfg):
    """Cheap tier: one text completion from Vertex AI."""
    from core.cost import usage_cost_inr

    p = _make_llm_provider(_cfg)
    result = p.respond(
        [{"role": "user", "content": "Reply with exactly: OK"}],
        tier="cheap",
        # Gemini 2.5 Flash uses reasoning tokens that count against max_tokens.
        # 10 tokens was exhausted by thinking with no budget left for output.
        params={"max_tokens": 128},
    )
    assert result.text, "Expected non-empty text response"

    # Issue 5: full usage assertions for every real Vertex call
    assert result.usage.prompt_tokens > 0, "real call must account prompt tokens"
    assert result.usage.completion_tokens > 0, "real call must have output tokens"
    assert result.usage.cost_native > 0, (
        f"result.usage.cost_native={result.usage.cost_native!r} — "
        "real Vertex call must return non-zero cost; check litellm pricing tables"
    )
    assert math.isfinite(result.usage.cost_native), "cost must be finite"
    assert result.usage.currency == "USD", "LiteLLM always reports in USD"

    cost_inr = usage_cost_inr(result.usage, fx_rates=_cfg["cost"]["fx_rates"])
    assert math.isfinite(cost_inr), "cost_inr must be finite"
    assert cost_inr > 0, "cost_inr must be positive"
    assert cost_inr < _SMOKE_COST_CAP_INR, f"cost Rs{cost_inr:.4f} >= cap Rs{_SMOKE_COST_CAP_INR}"


def test_smoke_structured_response(_cfg):
    """Cheap tier: one structured response from Vertex AI (validates JSON parsing + schema)."""
    from core.interfaces.base import CoreContractModel
    from core.cost import usage_cost_inr
    from pydantic import Field

    class _Greeting(CoreContractModel):
        message: str = Field(min_length=1)
        language: str = Field(min_length=1)

    p = _make_llm_provider(_cfg)
    result = p.respond(
        [{"role": "user", "content": "Respond with a greeting in English."}],
        tier="cheap",
        response_schema=_Greeting,
        # Gemini 2.5 Flash counts internal reasoning tokens against max_tokens.
        # Keep enough headroom for both reasoning and the small JSON payload.
        params={"max_tokens": 256},
    )
    assert result.structured is not None
    assert isinstance(result.structured, _Greeting)
    assert result.structured.message

    # Issue 5: full usage assertions for every real Vertex call
    assert result.usage.prompt_tokens > 0, "real call must account prompt tokens"
    assert result.usage.completion_tokens > 0, "real call must have output tokens"
    assert result.usage.cost_native > 0, "real call must have non-zero cost"
    assert math.isfinite(result.usage.cost_native), "cost must be finite"
    assert result.usage.currency == "USD", "LiteLLM always reports in USD"

    cost_inr = usage_cost_inr(result.usage, fx_rates=_cfg["cost"]["fx_rates"])
    assert math.isfinite(cost_inr), "cost_inr must be finite"
    assert cost_inr > 0, "cost_inr must be positive"
    assert cost_inr < _SMOKE_COST_CAP_INR, f"cost Rs{cost_inr:.4f} >= cap Rs{_SMOKE_COST_CAP_INR}"
