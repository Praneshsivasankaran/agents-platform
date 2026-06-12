"""Offline interface tests for LiteLLMProvider.

All litellm.completion calls are mocked via sys.modules injection.
No credentials or network needed. Works even if litellm is not installed.
"""
from __future__ import annotations
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest

from core.interfaces.llm import LLMProvider
from core.interfaces.base import CoreContractModel
from pydantic import Field


# ---------------------------------------------------------------------------
# Minimal Pydantic schema for structured output tests
# ---------------------------------------------------------------------------

class _FakeSchema(CoreContractModel):
    value: str = Field(min_length=1)
    count: int = Field(ge=0)


# Small schema used by Issue 3 schema-injection consistency test
class _SomeSchema(CoreContractModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

# Minimal config: uses vertex_ai models, has USD fx rate, has vertex_project set,
# and includes required per-token fallback pricing (Issue 2: now required at construction).
# Updated to use Gemini 2.5 models (2.0 Flash Lite and 2.0 Flash retired June 1 2026).
_MINIMAL_CFG = {
    "llm": {
        "provider": "litellm",
        "tier_models": {
            "cheap": "vertex_ai/gemini-2.5-flash",
            "strong": "vertex_ai/gemini-2.5-pro",
        },
        "vertex_project": "test-project",
        "vertex_location": "us-central1",
    },
    "cost": {
        "provider_currency": "USD",
        "fx_rates": {"USD": 83.0},
        "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
        "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
    },
}

# Config with fallback per-token pricing (enables cost fallback when litellm fails)
_MINIMAL_CFG_WITH_PRICING = {
    "llm": {
        "provider": "litellm",
        "tier_models": {
            "cheap": "vertex_ai/gemini-2.5-flash",
            "strong": "vertex_ai/gemini-2.5-pro",
        },
        "vertex_project": "test-project",
        "vertex_location": "us-central1",
    },
    "cost": {
        "provider_currency": "USD",
        "fx_rates": {"USD": 83.0},
        "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
        "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
    },
}

# Full config: both tiers, both pricing maps, all required fields.
# Used by Issue 2 and Issue 3 parametrized constructor tests.
_FULL_CFG = {
    "llm": {
        "provider": "litellm",
        "tier_models": {
            "cheap": "vertex_ai/gemini-2.5-flash",
            "strong": "vertex_ai/gemini-2.5-pro",
        },
        "vertex_project": "test-project",
        "vertex_location": "us-central1",
    },
    "cost": {
        "provider_currency": "USD",
        "fx_rates": {"USD": 83.0},
        "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
        "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
    },
}


# ---------------------------------------------------------------------------
# Helpers for building fake litellm responses
# ---------------------------------------------------------------------------

def _mock_litellm_response(content: str, prompt_tokens: int = 50, completion_tokens: int = 100):
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    return SimpleNamespace(choices=[choice], usage=usage)


def _make_litellm_module(completion_return=None, completion_cost_return=0.0,
                          completion_cost_side_effect=None):
    """Build a fake litellm module and register it in sys.modules."""
    mod = ModuleType("litellm")
    mock_completion = MagicMock(return_value=completion_return)
    mod.completion = mock_completion
    if completion_cost_side_effect is not None:
        mod.completion_cost = MagicMock(side_effect=completion_cost_side_effect)
    else:
        mod.completion_cost = MagicMock(return_value=completion_cost_return)
    return mod


# ---------------------------------------------------------------------------
# Context manager that injects a fake litellm module into sys.modules
# ---------------------------------------------------------------------------
from contextlib import contextmanager

@contextmanager
def _fake_litellm(completion_return=None, completion_cost_return=0.0,
                  completion_cost_side_effect=None):
    """Context manager: inject a fake litellm into sys.modules for the duration."""
    mod = _make_litellm_module(
        completion_return=completion_return,
        completion_cost_return=completion_cost_return,
        completion_cost_side_effect=completion_cost_side_effect,
    )
    prev = sys.modules.get("litellm", None)
    sys.modules["litellm"] = mod
    try:
        yield mod
    finally:
        if prev is None:
            sys.modules.pop("litellm", None)
        else:
            sys.modules["litellm"] = prev


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLiteLLMProviderInterface:
    def _make_provider(self):
        from core.providers.gcp.llm import LiteLLMProvider
        return LiteLLMProvider(_MINIMAL_CFG)

    def _make_provider_with_pricing(self):
        from core.providers.gcp.llm import LiteLLMProvider
        return LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)

    def test_is_llm_provider(self):
        from core.providers.gcp.llm import LiteLLMProvider
        assert isinstance(LiteLLMProvider(_MINIMAL_CFG), LLMProvider)

    def test_name(self):
        from core.providers.gcp.llm import LiteLLMProvider
        assert LiteLLMProvider(_MINIMAL_CFG).name == "litellm"

    def test_missing_tier_models_raises(self):
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {"llm": {"provider": "litellm", "tier_models": {}},
               "cost": {"fx_rates": {"USD": 83.0}}}
        with pytest.raises(ValueError, match="tier_models"):
            LiteLLMProvider(cfg)

    def test_missing_usd_fx_rate_raises(self):
        """Issue 2: USD must be in fx_rates since LiteLLM always returns USD costs."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {"llm": {"provider": "litellm",
                       "tier_models": {"cheap": "vertex_ai/foo", "strong": "vertex_ai/bar"}},
               "cost": {"fx_rates": {"EUR": 90.0}}}  # no USD
        with pytest.raises(ValueError, match="USD"):
            LiteLLMProvider(cfg)

    def test_unknown_tier_raises(self):
        p = self._make_provider()
        mock_resp = _mock_litellm_response("hi")
        with _fake_litellm(completion_return=mock_resp):
            with pytest.raises(ValueError, match="tier"):
                p.respond([{"role": "user", "content": "hi"}], tier="ultra")

    def test_text_response(self):
        p = self._make_provider()
        mock_resp = _mock_litellm_response("Hello, world!")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001) as mod:
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.text == "Hello, world!"
        assert result.structured is None
        mod.completion.assert_called_once()
        # Verify tier was resolved to cheap model
        call_kwargs = str(mod.completion.call_args)
        assert "vertex_ai/gemini-2.5-flash" in call_kwargs

    def test_strong_tier_uses_strong_model(self):
        p = self._make_provider()
        mock_resp = _mock_litellm_response("result")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.005) as mod:
            p.respond([{"role": "user", "content": "hi"}], tier="strong")
        call_kwargs = str(mod.completion.call_args)
        assert "vertex_ai/gemini-2.5-pro" in call_kwargs

    def test_usage_populated(self):
        p = self._make_provider()
        mock_resp = _mock_litellm_response("text", prompt_tokens=42, completion_tokens=17)
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.002):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.prompt_tokens == 42
        assert result.usage.completion_tokens == 17
        # Issue 2: currency is always USD
        assert result.usage.currency == "USD"

    def test_usage_missing_raises(self):
        from core.interfaces.errors import BillableProviderError
        p = self._make_provider()
        mock_resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=None,
        )
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.0):
            # After the provider call succeeds, missing usage → BillableProviderError (not plain ValueError)
            with pytest.raises(BillableProviderError):
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")

    def test_structured_response(self):
        p = self._make_provider()
        payload = {"value": "hello", "count": 3}
        mock_resp = _mock_litellm_response(json.dumps(payload))
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001):
            result = p.respond(
                [{"role": "user", "content": "give me schema"}],
                tier="cheap",
                response_schema=_FakeSchema,
            )
        assert result.structured is not None
        assert isinstance(result.structured, _FakeSchema)
        assert result.structured.value == "hello"
        assert result.structured.count == 3

    def test_structured_invalid_json_raises(self):
        from core.interfaces.errors import BillableProviderError
        p = self._make_provider()
        mock_resp = _mock_litellm_response("not json at all")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001):
            # After successful call + usage extraction, JSON parsing failure → BillableProviderError
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond(
                    [{"role": "user", "content": "hi"}],
                    tier="cheap",
                    response_schema=_FakeSchema,
                )
        # Cost must be preserved (real usage was extracted)
        assert exc_info.value.usage.cost_native > 0
        assert exc_info.value.usage.synthetic is False

    def test_structured_schema_violation_raises(self):
        """JSON that doesn't match the schema raises BillableProviderError."""
        from core.interfaces.errors import BillableProviderError
        p = self._make_provider()
        bad_payload = {"value": "", "count": -1}  # min_length=1, ge=0 violated
        mock_resp = _mock_litellm_response(json.dumps(bad_payload))
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond(
                    [{"role": "user", "content": "hi"}],
                    tier="cheap",
                    response_schema=_FakeSchema,
                )
        assert exc_info.value.usage.cost_native > 0
        assert exc_info.value.usage.synthetic is False

    def test_structured_output_passes_pydantic_model_directly(self):
        """response_format is the Pydantic model itself (LiteLLM documented form)."""
        from pydantic import BaseModel
        class _S(BaseModel):
            result: str
        p = self._make_provider()
        msgs = [{"role": "user", "content": "hi"}]
        msgs_out, kwargs = p._build_litellm_params(msgs, "cheap", None, _S)
        assert msgs_out == msgs, "messages must be unchanged"
        assert kwargs["response_format"] is _S, "response_format must be the Pydantic model"

    def test_params_forwarded(self):
        p = self._make_provider()
        mock_resp = _mock_litellm_response("ok")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001) as mod:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"max_tokens": 512})
        all_args = str(mod.completion.call_args)
        assert "512" in all_args

    def test_cost_native_from_litellm(self):
        p = self._make_provider()
        mock_resp = _mock_litellm_response("hi")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.0123):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert abs(result.usage.cost_native - 0.0123) < 1e-6

    # ---------------------------------------------------------------------------
    # Issue 1: Cost fallback and fail-closed behavior
    # ---------------------------------------------------------------------------

    def test_completion_cost_exception_falls_back_to_config_pricing(self):
        """When litellm.completion_cost raises, configured per-token pricing is used."""
        p = self._make_provider_with_pricing()
        mock_resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
        with _fake_litellm(
            completion_return=mock_resp,
            completion_cost_side_effect=Exception("no pricing"),
        ):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.cost_native > 0  # fallback pricing used

    def test_completion_cost_zero_falls_back_to_config_pricing(self):
        """When litellm.completion_cost returns 0, configured fallback pricing is used."""
        p = self._make_provider_with_pricing()
        mock_resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.0):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.cost_native > 0

    def test_no_pricing_at_all_raises_at_construction(self):
        """Missing pricing maps raise at construction (Issue 2: fail-closed pricing required)."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash", "strong": "vertex_ai/gemini-2.5-pro"},
                "vertex_project": "test-project",
                "vertex_location": "us-central1",
            },
            "cost": {
                "provider_currency": "USD",
                "fx_rates": {"USD": 83.0},
                # No input_cost_per_token_inr or output_cost_per_token_inr
            },
        }
        with pytest.raises(ValueError, match="missing"):
            LiteLLMProvider(cfg)

    # ---------------------------------------------------------------------------
    # Issue 2: Currency is always USD
    # ---------------------------------------------------------------------------

    def test_usage_currency_always_usd(self):
        """Even with provider_currency=EUR in config, Usage.currency is always USD."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/foo", "strong": "vertex_ai/bar"},
                "vertex_project": "test-project",
            },
            "cost": {
                "provider_currency": "EUR",
                "fx_rates": {"USD": 83.0, "EUR": 90.0},
                "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
                "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
            },
        }
        p = LiteLLMProvider(cfg)
        mock_resp = _mock_litellm_response("hi")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.005):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.currency == "USD"

    # ---------------------------------------------------------------------------
    # Issue 4: Vertex project/location forwarding
    # ---------------------------------------------------------------------------

    def test_vertex_project_forwarded_to_litellm(self):
        """vertex_project and vertex_location are passed to litellm.completion for vertex_ai models."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash", "strong": "vertex_ai/gemini-2.5-pro"},
                "vertex_project": "my-test-project",
                "vertex_location": "europe-west4",
            },
            "cost": {
                "fx_rates": {"USD": 83.0},
                "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
                "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
            },
        }
        p = LiteLLMProvider(cfg)
        mock_resp = _mock_litellm_response("ok")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001) as mod:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        all_args = str(mod.completion.call_args)
        assert "my-test-project" in all_args
        assert "europe-west4" in all_args

    def test_vertex_model_without_project_raises(self):
        """Calling respond() with a vertex_ai model but no project configured raises ValueError."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash", "strong": "vertex_ai/gemini-2.5-pro"},
            },
            "cost": {
                "fx_rates": {"USD": 83.0},
                "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
                "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
            },
        }
        p = LiteLLMProvider(cfg)
        mock_resp = _mock_litellm_response("ok")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001):
            with pytest.raises(ValueError, match="vertex_project"):
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")

    # ---------------------------------------------------------------------------
    # Issue 7: Tools parameter raises NotImplementedError
    # ---------------------------------------------------------------------------

    def test_non_empty_tools_raises_not_implemented(self):
        """Passing tools to LiteLLMProvider raises NotImplementedError (not silently ignored)."""
        p = self._make_provider()
        with pytest.raises(NotImplementedError, match="tool"):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      tools=[{"type": "function", "function": {"name": "test"}}])

    def test_empty_tools_ok(self):
        """Passing tools=None or tools=[] is fine."""
        p = self._make_provider()
        mock_resp = _mock_litellm_response("hi")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                               tools=None)
        assert result.text == "hi"

    def test_empty_tools_list_ok(self):
        """Passing tools=[] (empty list) is also fine."""
        p = self._make_provider()
        mock_resp = _mock_litellm_response("hi")
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.001):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                               tools=[])
        assert result.text == "hi"

    # ---------------------------------------------------------------------------
    # Issue 2 adversarial tests — fail-closed cost accounting
    # ---------------------------------------------------------------------------

    def test_none_usage_object_raises(self):
        """litellm response.usage=None → BillableProviderError (fail closed, cost preserved)."""
        from core.interfaces.errors import BillableProviderError
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)
        mock_resp = _mock_litellm_response("text")
        mock_resp.usage = None  # simulate missing usage
        with _fake_litellm(completion_return=mock_resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.usage.synthetic is True
        assert exc_info.value.usage.cost_native > 0
        assert exc_info.value.category == "usage_extraction_failed"

    def test_zero_tokens_nonempty_response_raises(self):
        """Zero prompt_tokens → BillableProviderError (broken usage, cost preserved)."""
        from core.interfaces.errors import BillableProviderError
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)
        mock_resp = _mock_litellm_response("non-empty content", prompt_tokens=0, completion_tokens=0)
        with _fake_litellm(completion_return=mock_resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        # category is content-free; raw message is never stored
        assert exc_info.value.category == "usage_extraction_failed"
        assert exc_info.value.usage.cost_native > 0

    def test_negative_pricing_rejected_at_construction(self):
        """Negative per-token pricing raises at construction."""
        from core.providers.gcp.llm import LiteLLMProvider
        bad_cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash",
                                "strong": "vertex_ai/gemini-2.5-pro"},
                "vertex_project": "test-project",
            },
            "cost": {
                "fx_rates": {"USD": 83.0},
                "output_cost_per_token_inr": {"cheap": -0.001, "strong": 0.005},
                "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
            },
        }
        with pytest.raises(ValueError, match="must be > 0"):
            LiteLLMProvider(bad_cfg)

    def test_zero_fx_rate_rejected(self):
        """Zero USD FX rate raises at construction."""
        from core.providers.gcp.llm import LiteLLMProvider
        bad_cfg = {
            "llm": {"provider": "litellm",
                    "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash",
                                    "strong": "vertex_ai/gemini-2.5-pro"},
                    "vertex_project": "test-project"},
            "cost": {"fx_rates": {"USD": 0.0}},
        }
        with pytest.raises(ValueError, match="fx_rate"):
            LiteLLMProvider(bad_cfg)

    def test_negative_fx_rate_rejected(self):
        """Negative USD FX rate raises at construction."""
        from core.providers.gcp.llm import LiteLLMProvider
        bad_cfg = {
            "llm": {"provider": "litellm",
                    "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash",
                                    "strong": "vertex_ai/gemini-2.5-pro"},
                    "vertex_project": "test-project"},
            "cost": {"fx_rates": {"USD": -83.0}},
        }
        with pytest.raises(ValueError, match="fx_rate"):
            LiteLLMProvider(bad_cfg)

    # ---------------------------------------------------------------------------
    # Issue 3 — schema must NOT modify messages; goes into response_format instead
    # ---------------------------------------------------------------------------

    def test_schema_does_not_modify_messages(self):
        """
        _build_litellm_params must NOT add message content when response_schema is set.
        The schema is passed via response_format (the Pydantic model itself), not as text
        in messages. This ensures Agent 01's token budget authorization covers the exact
        payload sent.
        """
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)
        messages = [{"role": "user", "content": "Write a blog"}]

        msgs_no_schema, _ = p._build_litellm_params(messages, "cheap", None, None)
        msgs_with_schema, kwargs_with_schema = p._build_litellm_params(messages, "cheap", None, _SomeSchema)

        # Messages must be identical — schema goes in response_format, not messages
        assert msgs_with_schema == msgs_no_schema, (
            "Schema must NOT be injected into messages; "
            "it belongs in response_format to avoid unauthorized token overhead"
        )
        # response_format is the Pydantic model itself (LiteLLM documented structured output;
        # LiteLLM handles the Vertex translation internally).
        assert kwargs_with_schema["response_format"] is _SomeSchema, (
            "response_format must be the Pydantic model itself"
        )

    # ---------------------------------------------------------------------------
    # Issue 4 — SecretStore enforcement
    # ---------------------------------------------------------------------------

    def test_vertex_project_secret_without_secret_store_raises(self):
        """vertex_project_secret without a SecretStore raises at construction."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash",
                                "strong": "vertex_ai/gemini-2.5-pro"},
                "vertex_project_secret": "VERTEX_AI_PROJECT",
            },
            "cost": {
                "fx_rates": {"USD": 83.0},
                "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
                "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
            },
        }
        with pytest.raises(ValueError, match="SecretStore"):
            LiteLLMProvider(cfg, secret_store=None)

    def test_vertex_project_secret_with_fake_secret_store(self):
        """vertex_project_secret resolved via SecretStore (no os.environ fallback)."""
        from core.providers.gcp.llm import LiteLLMProvider

        class _FakeSecretStore:
            def get(self, key: str):
                return "my-project-from-secret-store" if key == "VERTEX_AI_PROJECT" else None

        cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash",
                                "strong": "vertex_ai/gemini-2.5-pro"},
                "vertex_project_secret": "VERTEX_AI_PROJECT",
            },
            "cost": {
                "fx_rates": {"USD": 83.0},
                "input_cost_per_token_inr": {"cheap": 0.0001, "strong": 0.0005},
                "output_cost_per_token_inr": {"cheap": 0.001, "strong": 0.005},
            },
        }
        p = LiteLLMProvider(cfg, secret_store=_FakeSecretStore())
        assert p._vertex_project == "my-project-from-secret-store"


# ---------------------------------------------------------------------------
# Issue 1 — Gemini 2.5 Flash pricing correctness
# ---------------------------------------------------------------------------

# Reference USD prices (Vertex AI standard, June 2026)
_FLASH_INPUT_USD_PER_M = 0.30
_FLASH_OUTPUT_USD_PER_M = 2.50
_PRO_INPUT_USD_PER_M = 1.25
_PRO_OUTPUT_USD_PER_M = 10.00
_FX_RATE = 83.0


def test_flash_input_pricing_matches_official():
    """Configured Flash input price must equal official rate or be higher (pessimistic)."""
    import yaml
    import pathlib
    import math
    cfg_path = pathlib.Path("agents/agent-01-blog-writer/config/gcp.yaml")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    configured = cfg["cost"]["input_cost_per_token_inr"]["cheap"]
    expected = _FLASH_INPUT_USD_PER_M / 1_000_000 * _FX_RATE
    assert configured >= expected or math.isclose(configured, expected, rel_tol=1e-9), (
        f"Flash input price {configured} < official {expected:.10f} — "
        f"must not underestimate cost"
    )


def test_flash_output_pricing_matches_official():
    """Configured Flash output price must equal official rate or be higher (within float tolerance)."""
    import yaml
    import pathlib
    import math
    cfg_path = pathlib.Path("agents/agent-01-blog-writer/config/gcp.yaml")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    configured = cfg["cost"]["output_cost_per_token_inr"]["cheap"]
    expected = _FLASH_OUTPUT_USD_PER_M / 1_000_000 * _FX_RATE
    # Allow a tiny relative tolerance (1e-9) to handle IEEE-754 representation of
    # identical mathematical values. The key invariant is: configured >= expected.
    assert configured >= expected or math.isclose(configured, expected, rel_tol=1e-9), (
        f"Flash output price {configured} < official {expected:.10f} — "
        f"4x underestimate allows Rs50 ceiling to be breached"
    )


def test_ceiling_blocked_with_corrected_output_rate():
    """A Flash call producing enough output tokens must exceed the Rs50 ceiling."""
    # Rs50 / Rs0.0002075 ~= 241,000 output tokens to exceed ceiling
    output_tokens_at_boundary = 241_000
    output_cost_inr = output_tokens_at_boundary * (_FLASH_OUTPUT_USD_PER_M / 1_000_000 * _FX_RATE)
    assert output_cost_inr > 50.0, "Should exceed Rs50 ceiling at corrected output rate"


# ---------------------------------------------------------------------------
# Issue 2 — Adversarial usage extraction tests (fail-closed)
# ---------------------------------------------------------------------------

# Sentinel used in parametrize — represents a missing attribute
_ATTR_MISSING = object()


def _build_mock_response_with_usage(
    usage_obj=None,
    usage_is_none=False,
    prompt_override=_ATTR_MISSING,
    completion_override=_ATTR_MISSING,
):
    """Build a fake litellm response with controllable usage fields."""
    from types import SimpleNamespace
    content = "some text"
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    if usage_is_none:
        return SimpleNamespace(choices=[choice], usage=None)
    if usage_obj is not None:
        return SimpleNamespace(choices=[choice], usage=usage_obj)
    # Build a usage object with overridden fields
    base = SimpleNamespace(prompt_tokens=50, completion_tokens=100)
    if prompt_override is not _ATTR_MISSING:
        if prompt_override is _ATTR_MISSING:
            delattr(base, "prompt_tokens")
        else:
            base.prompt_tokens = prompt_override
    if completion_override is not _ATTR_MISSING:
        if completion_override is _ATTR_MISSING:
            delattr(base, "completion_tokens")
        else:
            base.completion_tokens = completion_override
    return SimpleNamespace(choices=[choice], usage=base)


class TestUsageExtractionFailClosed:
    """Issue 2: _extract_tokens must be fully fail-closed on all invalid inputs."""

    def _provider(self):
        from core.providers.gcp.llm import LiteLLMProvider
        return LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)

    def test_usage_none_raises(self):
        """response.usage=None → BillableProviderError (call succeeded, cost preserved)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=None,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.usage.synthetic is True
        assert exc_info.value.usage.cost_native > 0
        assert exc_info.value.category == "usage_extraction_failed"

    def test_prompt_tokens_missing_attribute_raises(self):
        """Usage object with no prompt_tokens attribute → BillableProviderError (cause: ValueError)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(completion_tokens=100)  # no prompt_tokens
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_completion_tokens_missing_attribute_raises(self):
        """Usage object with no completion_tokens → BillableProviderError (cause: ValueError)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=50)  # no completion_tokens
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_prompt_tokens_none_raises(self):
        """prompt_tokens=None → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=None, completion_tokens=100)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_completion_tokens_none_raises(self):
        """completion_tokens=None → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=50, completion_tokens=None)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_prompt_tokens_bool_true_raises(self):
        """prompt_tokens=True (bool) → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=True, completion_tokens=100)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_completion_tokens_bool_false_raises(self):
        """completion_tokens=False (bool) → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=50, completion_tokens=False)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_prompt_tokens_string_raises(self):
        """prompt_tokens='50' (string) → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens="50", completion_tokens=100)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_prompt_tokens_float_raises(self):
        """prompt_tokens=50.0 (float) → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=50.0, completion_tokens=100)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_prompt_tokens_negative_raises(self):
        """prompt_tokens=-1 → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=-1, completion_tokens=100)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_prompt_tokens_zero_raises(self):
        """prompt_tokens=0 → BillableProviderError (category: usage_extraction_failed)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        from types import SimpleNamespace
        usage = SimpleNamespace(prompt_tokens=0, completion_tokens=100)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=usage,
        )
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.category == "usage_extraction_failed"

    def test_litellm_cost_zero_uses_fallback(self):
        """litellm.completion_cost returning 0 falls through to configured fallback."""
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)
        mock_resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=0.0):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        # Fallback used — cost must be > 0 from configured pricing
        assert result.usage.cost_native > 0

    def test_litellm_cost_nan_uses_fallback(self):
        """NaN cost falls through to fallback."""
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)
        mock_resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=float("nan")):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.cost_native > 0

    def test_litellm_cost_negative_uses_fallback(self):
        """Negative cost falls through to fallback."""
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)
        mock_resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=-0.001):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.cost_native > 0

    def test_litellm_cost_inf_uses_fallback(self):
        """inf cost falls through to fallback."""
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_MINIMAL_CFG_WITH_PRICING)
        mock_resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
        with _fake_litellm(completion_return=mock_resp, completion_cost_return=float("inf")):
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.cost_native > 0

    def test_fallback_cost_zero_raises_at_construction(self):
        """Zero per-token rates raise at construction (Issue 2: must be > 0)."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = {
            "llm": {
                "provider": "litellm",
                "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash", "strong": "vertex_ai/gemini-2.5-pro"},
                "vertex_project": "test-project",
                "vertex_location": "us-central1",
            },
            "cost": {
                "fx_rates": {"USD": 83.0},
                "output_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
                "input_cost_per_token_inr": {"cheap": 0.0, "strong": 0.0},
            },
        }
        # Zero prices now rejected at construction — billing blindness guard
        with pytest.raises(ValueError, match="must be > 0"):
            LiteLLMProvider(cfg)


# ---------------------------------------------------------------------------
# Issue 6 — Constructor validation tests
# ---------------------------------------------------------------------------

# Base config used to build variations for constructor tests
_BASE_CFG = {
    "llm": {
        "provider": "litellm",
        "tier_models": {"cheap": "vertex_ai/gemini-2.5-flash", "strong": "vertex_ai/gemini-2.5-pro"},
        "vertex_project": "test-project",
        "vertex_location": "us-central1",
    },
    "cost": {
        "fx_rates": {"USD": 83.0},
        "output_cost_per_token_inr": {"cheap": 0.0002075, "strong": 0.00083},
        "input_cost_per_token_inr": {"cheap": 0.0000249, "strong": 0.0001037},
    },
}


def _cfg_copy():
    """Deep copy of _BASE_CFG to avoid mutation between tests."""
    import copy
    return copy.deepcopy(_BASE_CFG)


class TestConstructorValidation:
    """Issue 6: LiteLLMProvider must validate config aggressively at construction."""

    def test_missing_cheap_tier_raises(self):
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = _cfg_copy()
        cfg["llm"]["tier_models"] = {"strong": "vertex_ai/gemini-2.5-pro"}
        with pytest.raises(ValueError, match="cheap"):
            LiteLLMProvider(cfg)

    def test_missing_strong_tier_raises(self):
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = _cfg_copy()
        cfg["llm"]["tier_models"] = {"cheap": "vertex_ai/gemini-2.5-flash"}
        with pytest.raises(ValueError, match="strong"):
            LiteLLMProvider(cfg)

    def test_blank_model_id_raises(self):
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = _cfg_copy()
        cfg["llm"]["tier_models"] = {"cheap": "   ", "strong": "vertex_ai/gemini-2.5-pro"}
        with pytest.raises(ValueError, match="blank"):
            LiteLLMProvider(cfg)

    def test_non_string_model_id_raises(self):
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = _cfg_copy()
        cfg["llm"]["tier_models"] = {"cheap": 42, "strong": "vertex_ai/gemini-2.5-pro"}
        with pytest.raises(ValueError, match="string"):
            LiteLLMProvider(cfg)

    def test_blank_vertex_location_raises(self):
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = _cfg_copy()
        cfg["llm"]["vertex_location"] = ""
        with pytest.raises(ValueError, match="vertex_location"):
            LiteLLMProvider(cfg)

    def test_whitespace_vertex_location_raises(self):
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = _cfg_copy()
        cfg["llm"]["vertex_location"] = "   "
        with pytest.raises(ValueError, match="vertex_location"):
            LiteLLMProvider(cfg)

    def test_missing_fallback_pricing_for_configured_tier_raises(self):
        """Missing 'strong' from output pricing while it is in tier_models → ValueError."""
        from core.providers.gcp.llm import LiteLLMProvider
        cfg = _cfg_copy()
        # Keep only 'cheap' in fallback pricing; 'strong' tier is still in tier_models
        cfg["cost"]["output_cost_per_token_inr"] = {"cheap": 0.0002075}
        cfg["cost"]["input_cost_per_token_inr"] = {"cheap": 0.0000249}
        with pytest.raises(ValueError, match="strong"):
            LiteLLMProvider(cfg)

    def test_valid_config_constructs_ok(self):
        """Sanity: _BASE_CFG constructs without error."""
        from core.providers.gcp.llm import LiteLLMProvider
        p = LiteLLMProvider(_cfg_copy())
        assert p._vertex_location == "us-central1"
        assert p._tier_models["cheap"] == "vertex_ai/gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Issue 1 — Vertex structured-output format tests
# ---------------------------------------------------------------------------

def test_structured_output_passes_pydantic_model_directly():
    """response_format is the Pydantic model itself (LiteLLM documented form)."""
    import copy
    from pydantic import BaseModel
    from core.providers.gcp.llm import LiteLLMProvider

    class _S(BaseModel):
        result: str

    p = LiteLLMProvider(copy.deepcopy(_FULL_CFG))
    msgs = [{"role": "user", "content": "hi"}]
    msgs_out, kwargs = p._build_litellm_params(msgs, "cheap", None, _S)
    assert msgs_out == msgs, "messages must be unchanged"
    assert kwargs["response_format"] is _S, "response_format must be the Pydantic model"


def test_no_schema_no_response_format():
    """Without response_schema, response_format is not injected."""
    import copy
    from core.providers.gcp.llm import LiteLLMProvider

    p = LiteLLMProvider(copy.deepcopy(_FULL_CFG))
    msgs = [{"role": "user", "content": "hi"}]
    _, kwargs = p._build_litellm_params(msgs, "cheap", None, None)
    assert "response_format" not in kwargs


def test_structured_response_format_is_exact_model_no_dict_shape():
    """response_format must be the model object, never the old json_object/dict shape."""
    import copy
    from pydantic import BaseModel
    from core.providers.gcp.llm import LiteLLMProvider

    class _T(BaseModel):
        title: str
        score: int

    p = LiteLLMProvider(copy.deepcopy(_FULL_CFG))
    _, kwargs = p._build_litellm_params([{"role": "user", "content": "x"}], "cheap", None, _T)
    rf = kwargs["response_format"]
    assert rf is _T, "response_format must be the Pydantic model class itself"
    assert not isinstance(rf, dict), "response_format must NOT be a dict (old json_object shape)"


# ---------------------------------------------------------------------------
# Issue 2 — Exhaustive constructor pricing validation tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["input_cost_per_token_inr", "output_cost_per_token_inr"])
def test_missing_pricing_map_raises(missing):
    """Missing pricing map raises at construction."""
    import copy
    from core.providers.gcp.llm import LiteLLMProvider
    cfg = copy.deepcopy(_FULL_CFG)
    del cfg["cost"][missing]
    with pytest.raises(ValueError, match="missing"):
        LiteLLMProvider(cfg)


@pytest.mark.parametrize("tier", ["cheap", "strong"])
@pytest.mark.parametrize("map_name", ["input_cost_per_token_inr", "output_cost_per_token_inr"])
def test_missing_tier_entry_raises(map_name, tier):
    """Missing entry for a configured tier raises at construction."""
    import copy
    from core.providers.gcp.llm import LiteLLMProvider
    cfg = copy.deepcopy(_FULL_CFG)
    prices = dict(cfg["cost"][map_name])
    del prices[tier]
    cfg["cost"][map_name] = prices
    with pytest.raises(ValueError, match=tier):
        LiteLLMProvider(cfg)


@pytest.mark.parametrize("bad_val,match_str", [
    (0.0, "must be > 0"),
    (-0.001, "must be > 0"),
    (float("nan"), "not finite"),
    (float("inf"), "not finite"),
    (float("-inf"), "not finite"),
    (True, "bool"),
    ("0.001", "not numeric"),
])
def test_invalid_price_value_raises(bad_val, match_str):
    """Invalid per-token price values raise at construction."""
    import copy
    from core.providers.gcp.llm import LiteLLMProvider
    cfg = copy.deepcopy(_FULL_CFG)
    cfg["cost"]["output_cost_per_token_inr"]["cheap"] = bad_val
    with pytest.raises(ValueError, match=match_str):
        LiteLLMProvider(cfg)


# ---------------------------------------------------------------------------
# Issue 3 — Vertex project/location strict validation tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_val,match_str", [
    ("", "empty"),
    ("   ", "whitespace"),
    (123, "must be a string"),
])
def test_blank_vertex_project_direct_raises(bad_val, match_str):
    import copy
    from core.providers.gcp.llm import LiteLLMProvider
    cfg = copy.deepcopy(_FULL_CFG)
    cfg["llm"]["vertex_project"] = bad_val
    with pytest.raises(ValueError, match=match_str):
        LiteLLMProvider(cfg)


@pytest.mark.parametrize("bad_val,match_str", [
    (None, "empty"),
    ("", "empty"),
    ("   ", "whitespace"),
    (42, "must be a string"),
])
def test_blank_vertex_project_from_secret_store_raises(bad_val, match_str):
    import copy
    from core.providers.gcp.llm import LiteLLMProvider

    class _BadStore:
        def get(self, key: str):
            return bad_val

    cfg = copy.deepcopy(_FULL_CFG)
    del cfg["llm"]["vertex_project"]
    cfg["llm"]["vertex_project_secret"] = "MY_PROJECT"
    with pytest.raises(ValueError, match=match_str):
        LiteLLMProvider(cfg, secret_store=_BadStore())


@pytest.mark.parametrize("bad_val,match_str", [
    ("", "empty"),
    ("   ", "whitespace"),
    (None, "empty"),    # None from config treated as absent/empty
    (123, "must be a string"),
])
def test_invalid_vertex_location_raises(bad_val, match_str):
    import copy
    from core.providers.gcp.llm import LiteLLMProvider
    cfg = copy.deepcopy(_FULL_CFG)
    cfg["llm"]["vertex_location"] = bad_val
    with pytest.raises(ValueError, match=match_str):
        LiteLLMProvider(cfg)


def test_vertex_location_stripped():
    """vertex_location value is stored stripped (no leading/trailing whitespace)."""
    import copy
    from core.providers.gcp.llm import LiteLLMProvider
    cfg = copy.deepcopy(_FULL_CFG)
    cfg["llm"]["vertex_location"] = "  us-central1  "
    p = LiteLLMProvider(cfg)
    assert p._vertex_location == "us-central1"


def test_vertex_project_stripped():
    """Direct vertex_project value is stored stripped."""
    import copy
    from core.providers.gcp.llm import LiteLLMProvider
    cfg = copy.deepcopy(_FULL_CFG)
    cfg["llm"]["vertex_project"] = "  my-project  "
    p = LiteLLMProvider(cfg)
    assert p._vertex_project == "my-project"


# ---------------------------------------------------------------------------
# Item 4 — BillableProviderError adversarial tests
# ---------------------------------------------------------------------------

class TestBillableProviderError:
    """Adversarial tests for BillableProviderError from LiteLLMProvider.respond()."""

    def _provider(self):
        import copy
        from core.providers.gcp.llm import LiteLLMProvider
        return LiteLLMProvider(copy.deepcopy(_FULL_CFG))

    def test_missing_usage_raises_billable_error_not_plain_value_error(self):
        """After a successful litellm call, missing usage → BillableProviderError."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=25)
        resp.usage = None
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        err = exc_info.value
        assert err.usage.cost_native > 0, "conservative usage must have positive cost"
        assert err.usage.synthetic is True, "conservative usage must be synthetic"
        assert err.category == "usage_extraction_failed"
        # No raw response content in message
        assert "text" not in str(err), "raw response content must not appear in error message"

    def test_usage_extraction_failure_raises_billable_error(self):
        """Boolean prompt_tokens → BillableProviderError with conservative cost."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        resp = _mock_litellm_response("text")
        resp.usage.prompt_tokens = True  # bool triggers extraction failure
        with _fake_litellm(completion_return=resp):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.usage.cost_native > 0

    def test_invalid_json_raises_billable_error_after_successful_call(self):
        """Invalid JSON in response after successful call → BillableProviderError."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        resp = _mock_litellm_response("NOT_VALID_JSON", prompt_tokens=50, completion_tokens=25)
        with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                          response_schema=_FakeSchema)
        err = exc_info.value
        assert err.usage.cost_native > 0
        assert err.usage.synthetic is False  # usage was successfully extracted before parse fail
        # No raw response content in message
        assert "NOT_VALID_JSON" not in str(err)

    def test_schema_validation_failure_raises_billable_error(self):
        """Valid JSON but wrong schema → BillableProviderError."""
        from core.interfaces.errors import BillableProviderError
        from pydantic import BaseModel
        class _S(CoreContractModel):
            required_field: int  # missing in response
        p = self._provider()
        resp = _mock_litellm_response(
            json.dumps({"wrong_field": "value"}),
            prompt_tokens=50, completion_tokens=25
        )
        with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                          response_schema=_S)
        assert exc_info.value.usage.cost_native > 0

    def test_bad_choices_structure_raises_billable_error(self):
        """Broken choices structure after call → BillableProviderError."""
        from core.interfaces.errors import BillableProviderError

        class _RaisesOnContent:
            @property
            def content(self):
                raise AttributeError("no content attr")

        class _RaisesOnMessage:
            message = _RaisesOnContent()

        p = self._provider()
        resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=25)
        # Replace choices with a list where accessing .message.content raises
        resp.choices = [_RaisesOnMessage()]
        with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert exc_info.value.usage.cost_native > 0

    def test_pre_call_failure_is_not_billable(self):
        """Failure before litellm.completion() (tools validation) is NOT BillableProviderError."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        # tools raises NotImplementedError BEFORE the call
        with pytest.raises(NotImplementedError):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      tools=[{"type": "function", "function": {"name": "f"}}])

    def test_litellm_cost_calculation_failure_uses_fallback_not_billable_error(self):
        """litellm.completion_cost() failure falls back to config pricing (not BillableProviderError)."""
        from core.interfaces.errors import BillableProviderError
        p = self._provider()
        resp = _mock_litellm_response("ok", prompt_tokens=50, completion_tokens=25)
        with _fake_litellm(
            completion_return=resp,
            completion_cost_side_effect=Exception("no data"),
        ):
            # Should succeed using fallback pricing (not raise BillableProviderError)
            result = p.respond([{"role": "user", "content": "hi"}], tier="cheap")
        assert result.usage.cost_native > 0

    def test_billable_error_category_is_allowlisted(self):
        """BillableProviderError.category is an allowlisted, content-free string (not a class name)."""
        from core.interfaces.errors import BillableProviderError, BILLABLE_FAILURE_CATEGORIES
        p = self._provider()
        resp = _mock_litellm_response("NOT_JSON", prompt_tokens=50, completion_tokens=25)
        with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
            with pytest.raises(BillableProviderError) as exc_info:
                p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                          response_schema=_FakeSchema)
        # JSON parse failure → json_parse_failed category (never a class name)
        assert exc_info.value.category == "json_parse_failed"
        assert exc_info.value.category in BILLABLE_FAILURE_CATEGORIES

    def test_billable_error_picklable(self):
        """BillableProviderError can be pickled (required for checkpointing)."""
        import pickle
        from core.interfaces.errors import BillableProviderError
        from core.interfaces.usage import Usage
        usage = Usage(
            prompt_tokens=100, completion_tokens=200,
            cost_native=0.001, currency="USD", synthetic=True,
        )
        err = BillableProviderError(usage, "usage_extraction_failed")
        pickled = pickle.dumps(err)
        restored = pickle.loads(pickled)
        assert restored.usage.prompt_tokens == 100
        assert restored.usage.cost_native > 0
        assert restored.category == "usage_extraction_failed"


# ---------------------------------------------------------------------------
# Issue 1 — Conservative usage must use authorized prompt tokens, not word count
# ---------------------------------------------------------------------------

def test_conservative_usage_uses_authorized_estimate_not_word_count():
    """Conservative usage uses _authorized_prompt_tokens, not word-count guess."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
    resp.usage = None  # force conservative path

    # Large 10k-char prompt
    long_content = "x" * 10_000
    messages = [{"role": "user", "content": long_content}]

    # Without _authorized_prompt_tokens: estimate_prompt_tokens uses 1 token/UTF-8 byte
    # (>= 10000 for this ASCII content), so the conservative estimate is well above 2500.
    with _fake_litellm(completion_return=resp):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond(messages, tier="cheap", params=None)
    assert exc_info.value.usage.prompt_tokens >= 2500, (
        f"Without authorized estimate, should use estimate_prompt_tokens (1 token/byte); "
        f"got {exc_info.value.usage.prompt_tokens}"
    )

    # With _authorized_prompt_tokens: must use that value exactly
    with _fake_litellm(completion_return=resp):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond(messages, tier="cheap", params={"_authorized_prompt_tokens": 9500})
    assert exc_info.value.usage.prompt_tokens == 9500, (
        f"Conservative usage must use _authorized_prompt_tokens exactly; "
        f"got {exc_info.value.usage.prompt_tokens}"
    )


def test_conservative_usage_uses_byte_based_estimate_for_dense_text():
    """Conservative usage uses estimate_prompt_tokens (1 token/UTF-8 byte) for dense text."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text")
    resp.usage = None

    # CJK: 5000 chars, each 3 UTF-8 bytes → 15000 bytes → estimate well above 1250.
    cjk_content = "测试" * 2500  # 5000 chars
    messages = [{"role": "user", "content": cjk_content}]
    with _fake_litellm(completion_return=resp):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond(messages, tier="cheap")
    # 1 token/UTF-8 byte → >= 1250 (in fact ~15000).
    assert exc_info.value.usage.prompt_tokens >= 1250, (
        f"byte-based estimate should give >=1250; got {exc_info.value.usage.prompt_tokens}"
    )
    assert exc_info.value.usage.cost_native > 0


# ---------------------------------------------------------------------------
# Issue 2 — litellm.completion() exceptions must be billable
# ---------------------------------------------------------------------------

def test_litellm_timeout_raises_billable_error():
    """A timeout during litellm.completion raises BillableProviderError (may have been billed)."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = TimeoutError("connection timed out")
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_authorized_prompt_tokens": 100})
    err = exc_info.value
    assert err.usage.cost_native > 0
    assert err.usage.synthetic is True
    assert err.category == "provider_call_failed"


def test_litellm_connection_error_raises_billable_error():
    """A connection error during the call raises BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = ConnectionError("connection reset")
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


def test_pre_call_failure_remains_non_billable():
    """Failures before litellm.completion() (e.g. tools check) are NOT BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(NotImplementedError):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      tools=[{"type": "function", "function": {"name": "f"}}])
        mod.completion.assert_not_called()


# ---------------------------------------------------------------------------
# Issue 3 — Pickling BillableProviderError must not leak raw response content
# ---------------------------------------------------------------------------

def _make_test_usage():
    from core.interfaces.usage import Usage
    return Usage(
        prompt_tokens=100, completion_tokens=50,
        cost_native=0.001, currency="USD", synthetic=False,
    )


def test_billable_error_pickle_does_not_leak_raw_content():
    """Pickling a BillableProviderError raised through respond() preserves no raw content."""
    import pickle
    from core.interfaces.errors import BillableProviderError
    from core.providers.gcp.llm import LiteLLMProvider

    p = LiteLLMProvider(_FULL_CFG)
    # Invalid JSON containing a secret value, parsed structurally through respond().
    resp = _mock_litellm_response('NOT_VALID_JSON SECRET_VALUE_12345',
                                  prompt_tokens=50, completion_tokens=25)
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      response_schema=_FakeSchema)
    err = exc_info.value
    # str(err) must not leak content
    assert "SECRET_VALUE_12345" not in str(err)
    # pickle/unpickle must not leak content
    unpickled = pickle.loads(pickle.dumps(err))
    assert "SECRET_VALUE_12345" not in str(unpickled)
    assert "SECRET_VALUE_12345" not in unpickled.category
    assert "SECRET_VALUE_12345" not in repr(unpickled)


def test_billable_error_category_preserved_in_pickle():
    """After pickling, category is preserved (content-free allowlisted string)."""
    import pickle
    from core.interfaces.errors import BillableProviderError, BILLABLE_FAILURE_CATEGORIES

    err = BillableProviderError(_make_test_usage(), "usage_extraction_failed")
    unpickled = pickle.loads(pickle.dumps(err))
    assert unpickled.category == "usage_extraction_failed"
    assert unpickled.category in BILLABLE_FAILURE_CATEGORIES
    # No raw exception object stored
    assert not hasattr(unpickled, "cause") or not isinstance(getattr(unpickled, "cause", None), Exception)


def test_billable_error_non_allowlisted_category_coerced_to_unknown():
    """A category outside the allowlist is coerced to 'unknown' (content-free)."""
    from core.interfaces.errors import BillableProviderError
    err = BillableProviderError(_make_test_usage(), "RuntimeError: secret leaked here")
    assert err.category == "unknown"


# ---------------------------------------------------------------------------
# Issue 4 — Malformed text responses must raise BillableProviderError
# ---------------------------------------------------------------------------

def test_empty_choices_raises_billable_error():
    """Empty choices list after successful call → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=25)
    resp.choices = []
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.synthetic is False  # usage was extracted successfully
    assert exc_info.value.usage.cost_native > 0


def test_none_choices_raises_billable_error():
    """None choices after successful call → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=25)
    resp.choices = None
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


def test_none_message_raises_billable_error():
    """None message in choices → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=25)
    resp.choices[0].message = None
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


def test_none_content_raises_billable_error():
    """content=None (no text response) → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=25)
    resp.choices[0].message.content = None
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


# ---------------------------------------------------------------------------
# Issue 1 — _authorized_prompt_tokens validation and forwarding
# ---------------------------------------------------------------------------

def test_internal_params_not_forwarded_to_litellm():
    """_authorized_prompt_tokens must not appear in litellm.completion() kwargs."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("ok", prompt_tokens=100, completion_tokens=50)
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001) as mod:
        p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                  params={"max_tokens": 512, "_authorized_prompt_tokens": 200})
    call_kwargs = mod.completion.call_args
    all_args_str = str(call_kwargs)
    assert "_authorized_prompt_tokens" not in all_args_str


def test_invalid_authorized_tokens_bool_fails_before_call():
    """_authorized_prompt_tokens=True (bool) raises ValueError before calling litellm."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match="_authorized_prompt_tokens"):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_authorized_prompt_tokens": True})
        mod.completion.assert_not_called()


def test_invalid_authorized_tokens_negative_fails_before_call():
    """_authorized_prompt_tokens=-1 raises ValueError before calling litellm."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match="_authorized_prompt_tokens"):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_authorized_prompt_tokens": -1})
        mod.completion.assert_not_called()


def test_authorized_tokens_used_exactly_in_conservative_usage():
    """_authorized_prompt_tokens=9500 → prompt_tokens=9500 in conservative usage."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=100, completion_tokens=50)
    resp.usage = None  # force conservative path

    cjk_content = "测试" * 2500  # 5000 CJK chars
    messages = [{"role": "user", "content": cjk_content}]
    with _fake_litellm(completion_return=resp):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond(messages, tier="cheap", params={"_authorized_prompt_tokens": 9500})
    assert exc_info.value.usage.prompt_tokens == 9500, (
        f"Conservative usage must use _authorized_prompt_tokens exactly; "
        f"got {exc_info.value.usage.prompt_tokens}"
    )


# ---------------------------------------------------------------------------
# Issue 2 — BillableProviderError canary / security tests
# ---------------------------------------------------------------------------

_CANARY = "CANARY_SECRET_7x3k9_MUST_NOT_LEAK"


def _canary_absent_everywhere(err, *, label):
    """Assert canary is absent in every serialization/chaining form of err."""
    import pickle
    import copy
    checks = {
        "str": str(err),
        "repr": repr(err),
        "args": str(err.args),
        "__dict__": str(getattr(err, "__dict__", "")),
        "__cause__": str(err.__cause__),
        "__context__": str(err.__context__),
        "pickle": str(pickle.loads(pickle.dumps(err))),
        "pickle__dict__": str(pickle.loads(pickle.dumps(err)).__dict__),
        "deepcopy": str(copy.deepcopy(err)),
    }
    for form, val in checks.items():
        assert _CANARY not in val, f"{label}.{form} leaked canary: {val[:200]!r}"


def test_respond_jsondecode_failure_no_canary_via_respond():
    """Trigger json_parse_failed THROUGH respond() and assert canary absent + chaining cleared."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response(f'NOT JSON {_CANARY}', prompt_tokens=50, completion_tokens=25)
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        try:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap", response_schema=_FakeSchema)
            assert False, "should have raised"
        except BillableProviderError as err:
            assert err.__cause__ is None, "__cause__ must be None"
            assert err.__context__ is None, "__context__ must be None"
            assert err.category == "json_parse_failed"
            _canary_absent_everywhere(err, label="json_parse")


def test_respond_provider_call_exception_no_canary():
    """litellm.completion raising an exception with canary in message → no leak."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = RuntimeError(f"boom {_CANARY}")
        try:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_authorized_prompt_tokens": 100})
            assert False
        except BillableProviderError as err:
            assert err.__cause__ is None
            assert err.__context__ is None
            assert err.category == "provider_call_failed"
            _canary_absent_everywhere(err, label="provider_call")


def test_respond_usage_extraction_failure_no_canary():
    """usage extraction failure with canary → no leak."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("ok", prompt_tokens=50, completion_tokens=25)
    resp.usage.prompt_tokens = f"bad {_CANARY}"  # string → extraction error
    with _fake_litellm(completion_return=resp):
        try:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
            assert False
        except BillableProviderError as err:
            assert err.__cause__ is None
            assert err.__context__ is None
            assert err.category == "usage_extraction_failed"
            _canary_absent_everywhere(err, label="usage_extraction")


def test_billable_error_chaining_cleared_when_constructed():
    """A directly-constructed BillableProviderError has __cause__/__context__ None."""
    from core.interfaces.errors import BillableProviderError
    err = BillableProviderError(_make_test_usage(), "json_parse_failed")
    assert err.__cause__ is None
    assert err.__context__ is None


# ---------------------------------------------------------------------------
# Issue 1 — Conservative fallback must include schema overhead
# ---------------------------------------------------------------------------

def test_conservative_fallback_includes_schema_overhead():
    """Without _authorized_prompt_tokens, structured fallback adds schema overhead."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError

    class _Small(CoreContractModel):
        x: str

    class _Big(CoreContractModel):
        a: str; b: str; c: str; d: str; e: str; f: str; g: str; h: str

    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text")
    resp.usage = None  # force conservative path
    msgs = [{"role": "user", "content": "hi"}]

    def _cap(schema):
        with _fake_litellm(completion_return=resp):
            try:
                p.respond(msgs, tier="cheap", response_schema=schema)  # no _authorized_prompt_tokens
            except BillableProviderError as e:
                return e.usage.prompt_tokens

    no_schema = _cap(None)
    small = _cap(_Small)
    big = _cap(_Big)
    assert small > no_schema, "schema adds overhead"
    assert big > small, "bigger schema adds more overhead"


def test_conservative_fallback_matches_node_authorized_estimate():
    """estimate_prompt_tokens used in fallback == what a node would authorize for same request."""
    from core.cost import estimate_prompt_tokens
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError

    class _S(CoreContractModel):
        result: str

    msgs = [{"role": "user", "content": "Write a blog about cats"}]
    node_estimate = estimate_prompt_tokens(msgs, response_schema=_S)

    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text")
    resp.usage = None
    with _fake_litellm(completion_return=resp):
        try:
            p.respond(msgs, tier="cheap", response_schema=_S)  # no authorized → fallback
            assert False
        except BillableProviderError as e:
            assert e.usage.prompt_tokens == node_estimate, (
                f"fallback {e.usage.prompt_tokens} != node estimate {node_estimate}"
            )


def test_authorized_tokens_still_preferred_over_fallback():
    """When _authorized_prompt_tokens is supplied, it wins over the schema estimate."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError

    class _S(CoreContractModel):
        result: str

    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text")
    resp.usage = None
    with _fake_litellm(completion_return=resp):
        try:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      response_schema=_S, params={"_authorized_prompt_tokens": 7777})
            assert False
        except BillableProviderError as e:
            assert e.usage.prompt_tokens == 7777


def test_invalid_content_fails_before_provider_call():
    """Non-string content is caught by pre-call validation; litellm.completion never called."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    bad_msgs = [{"role": "user", "content": 12345}]
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match="content"):
            p.respond(bad_msgs, tier="cheap")
        # Provider was never called — no cost was incurred.
        mod.completion.assert_not_called()


def test_node_billable_error_carries_only_category_and_usage():
    """A BillableProviderError exposes only content-free category + usage for node conversion."""
    from core.interfaces.errors import BillableProviderError
    from core.interfaces.usage import Usage

    # Build a content-free BillableProviderError (categories are safe by design).
    usage = Usage(prompt_tokens=100, completion_tokens=50,
                  cost_native=0.001, currency="USD", synthetic=True)
    bpe = BillableProviderError(usage, "json_parse_failed")
    # The only data a node may read: category (allowlisted) + usage. No raw exception,
    # and chaining is clear so attaching bpe as context cannot leak provider content.
    assert bpe.__cause__ is None and bpe.__context__ is None
    assert bpe.category == "json_parse_failed"
    assert not hasattr(bpe, "cause")
    # The content-free message a node forwards.
    node_message = f"billable-provider-failure:{bpe.category}"
    assert _CANARY not in node_message
    assert bpe.usage.prompt_tokens == 100


# ---------------------------------------------------------------------------
# Issue 3 — Malformed blank/non-string responses raise BillableProviderError
# ---------------------------------------------------------------------------

def test_empty_string_content_raises_billable_error():
    """Empty string content after successful call → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("", prompt_tokens=50, completion_tokens=0)
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


def test_whitespace_only_content_raises_billable_error():
    """Whitespace-only content → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("   \n\t  ", prompt_tokens=50, completion_tokens=5)
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


def test_integer_content_raises_billable_error():
    """Integer content (not a str) → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=5)
    resp.choices[0].message.content = 42  # integer, not str
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


def test_dict_content_raises_billable_error():
    """Dict content (not a str) → BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=5)
    resp.choices[0].message.content = {"key": "value"}
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001):
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap")
    assert exc_info.value.usage.cost_native > 0


# ---------------------------------------------------------------------------
# Issue 1 — estimate_prompt_tokens standalone tests
# ---------------------------------------------------------------------------

def test_estimate_prompt_tokens_ascii_conservative():
    """ASCII prompts are estimated conservatively (never under-counted)."""
    from core.cost import estimate_prompt_tokens
    msgs = [{"role": "user", "content": "Hello world " * 100}]  # 1200 chars
    est = estimate_prompt_tokens(msgs)
    # "Hello world " is ~3 tokens per 12 chars = 100 tokens real
    # Our estimate should be >= 100
    assert est >= 100


def test_estimate_prompt_tokens_large_conservative():
    """10000 char prompt gives estimate >= 3000."""
    from core.cost import estimate_prompt_tokens
    msgs = [{"role": "user", "content": "x" * 10000}]
    est = estimate_prompt_tokens(msgs)
    assert est >= 3000, f"Expected >= 3000, got {est}"


def test_estimate_prompt_tokens_cjk_conservative():
    """CJK prompts are estimated conservatively."""
    from core.cost import estimate_prompt_tokens
    msgs = [{"role": "user", "content": "你好世界" * 1000}]  # 4000 CJK chars
    est = estimate_prompt_tokens(msgs)
    # Must be significantly more than 256
    assert est > 300, f"CJK estimate too low: {est}"


def test_estimate_prompt_tokens_with_schema_overhead():
    """Schema overhead is included in token estimate."""
    from core.cost import estimate_prompt_tokens
    from pydantic import BaseModel
    class _S(BaseModel):
        result: str
        reason: str

    msgs = [{"role": "user", "content": "hi"}]
    without_schema = estimate_prompt_tokens(msgs)
    with_schema = estimate_prompt_tokens(msgs, response_schema=_S)
    assert with_schema > without_schema, "Schema must add to estimate"


# ---------------------------------------------------------------------------
# Repair Pass 9 — pre-call validation and conservative-usage pre-computation
# ---------------------------------------------------------------------------

def _walk_exception_chain(err):
    """Return all exceptions in the __cause__ / __context__ chain (breadth-first, cycle-safe)."""
    seen = set()
    result = []
    queue = [err]
    while queue:
        e = queue.pop(0)
        if e is None or id(e) in seen:
            continue
        seen.add(id(e))
        result.append(e)
        if getattr(e, "__cause__", None) is not None:
            queue.append(e.__cause__)
        if getattr(e, "__context__", None) is not None:
            queue.append(e.__context__)
    return result


_PASS9_CANARY = "CANARY_PASS9_MUST_NOT_LEAK_xk7q"


@pytest.mark.parametrize("bad_msgs,match", [
    ([{"role": "user", "content": 12345}],        "content"),
    ([{"role": "user", "content": {}}],            "content"),
    ([{"role": "user", "content": []}],            "content"),
    ([{"role": "user", "content": None}],          "content"),
    ([{"role": "", "content": "hi"}],              "role"),
    ([{"role": 123, "content": "hi"}],             "role"),
    ([{"content": "hi"}],                          "role"),
    ([{"role": "user"}],                           "content"),
    ("not a list",                                 "list"),
    ([42],                                         "dict"),
])
def test_invalid_messages_fail_before_provider_call(bad_msgs, match):
    """Malformed messages raise ValueError before litellm.completion() is invoked."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match=match):
            p.respond(bad_msgs, tier="cheap")
        mod.completion.assert_not_called()


def test_invalid_content_with_canary_provider_exception_canary_never_appears():
    """Non-string content prevents the provider call; the canary exception is never triggered."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    bad_msgs = [{"role": "user", "content": 12345}]
    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = RuntimeError(f"boom {_PASS9_CANARY}")
        with pytest.raises(ValueError) as exc_info:
            p.respond(bad_msgs, tier="cheap")
        mod.completion.assert_not_called()
    # Walk every node in the exception chain — canary must be absent everywhere.
    chain = _walk_exception_chain(exc_info.value)
    for exc in chain:
        assert _PASS9_CANARY not in str(exc), (
            f"Canary leaked through exception chain node {exc!r}"
        )


def test_provider_timeout_after_valid_precomputation_billable_no_chain():
    """Provider timeout after valid pre-computation → chaining-free BillableProviderError."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = RuntimeError(f"timeout {_PASS9_CANARY}")
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_authorized_prompt_tokens": 200})
    err = exc_info.value
    assert err.__cause__ is None, f"__cause__ must be None, got {err.__cause__!r}"
    assert err.__context__ is None, f"__context__ must be None, got {err.__context__!r}"
    assert err.category == "provider_call_failed"
    assert err.usage.cost_native > 0
    assert err.usage.synthetic is True
    # Canary must not appear anywhere in the chain.
    for exc in _walk_exception_chain(err):
        assert _PASS9_CANARY not in str(exc)


def test_malformed_usage_after_provider_success_uses_precomputed_usage():
    """Malformed usage after a successful call uses pre-computed conservative usage."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    resp = _mock_litellm_response("text", prompt_tokens=50, completion_tokens=25)
    resp.usage = None  # force usage_extraction_failed path
    with _fake_litellm(completion_return=resp) as mod:
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_authorized_prompt_tokens": 300})
    err = exc_info.value
    assert err.category == "usage_extraction_failed"
    assert err.usage.cost_native > 0
    assert err.usage.synthetic is True
    # Pre-computed usage uses _authorized_prompt_tokens=300.
    assert err.usage.prompt_tokens == 300
    # No chaining.
    assert err.__cause__ is None
    assert err.__context__ is None


def test_structured_precomputed_conservative_includes_schema_overhead():
    """Pre-computed conservative usage for a structured call includes schema overhead."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError

    class _S(CoreContractModel):
        result: str

    p = LiteLLMProvider(_FULL_CFG)
    msgs = [{"role": "user", "content": "Write a blog"}]

    resp_no_schema = _mock_litellm_response("text")
    resp_no_schema.usage = None
    resp_with_schema = _mock_litellm_response("text")
    resp_with_schema.usage = None

    with _fake_litellm(completion_return=resp_no_schema):
        try:
            p.respond(msgs, tier="cheap")
        except BillableProviderError as e:
            tokens_no_schema = e.usage.prompt_tokens

    with _fake_litellm(completion_return=resp_with_schema):
        try:
            p.respond(msgs, tier="cheap", response_schema=_S)
        except BillableProviderError as e:
            tokens_with_schema = e.usage.prompt_tokens

    assert tokens_with_schema > tokens_no_schema, (
        f"Schema overhead must increase conservative estimate: "
        f"{tokens_with_schema} > {tokens_no_schema}"
    )


def test_invalid_max_tokens_fails_before_provider_call():
    """Invalid max_tokens (zero, negative, bool) raises ValueError before litellm is called."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    msgs = [{"role": "user", "content": "hi"}]
    for bad_val in (-1, 0, True):
        with _fake_litellm(completion_return=None) as mod:
            with pytest.raises(ValueError, match="max_tokens"):
                p.respond(msgs, tier="cheap", params={"max_tokens": bad_val})
            mod.completion.assert_not_called()


def test_unknown_internal_param_fails_before_provider_call():
    """Unknown _-prefixed param raises ValueError before litellm is called."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match="_unknown_internal"):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_unknown_internal": "bad"})
        mod.completion.assert_not_called()


def test_precomputed_conservative_usage_canary_recursive_chain_clean():
    """Full recursive exception-chain walk — canary absent at every depth after provider call."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = RuntimeError(f"raw-provider {_PASS9_CANARY}")
        try:
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      params={"_authorized_prompt_tokens": 100})
            assert False, "should have raised"
        except BillableProviderError as err:
            chain = _walk_exception_chain(err)
            for exc in chain:
                assert _PASS9_CANARY not in str(exc), (
                    f"Canary leaked in chain node {exc!r}"
                )
            # Exactly one node in the chain — no __cause__ or __context__.
            assert len(chain) == 1, (
                f"Expected exactly 1 exception in chain, got {len(chain)}: {chain}"
            )


# ---------------------------------------------------------------------------
# Repair Pass 10 — unknown message fields and invalid response_schema
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_msgs,match_str", [
    # Unknown extra field — not accounted for by estimate_prompt_tokens
    ([{"role": "user", "content": "hi", "name": "alice"}],      "unknown keys"),
    ([{"role": "user", "content": "hi", "tool_call_id": "x"}],  "unknown keys"),
    # Empty list — nothing to bill, but still wrong
    ([],                                                          "non-empty"),
    # Blank / whitespace-only content — cannot be priced safely
    ([{"role": "user", "content": ""}],                          "empty or whitespace"),
    ([{"role": "user", "content": "   "}],                       "empty or whitespace"),
    ([{"role": "user", "content": "\t\n"}],                      "empty or whitespace"),
])
def test_invalid_message_fields_fail_before_provider(bad_msgs, match_str):
    """Malformed/unknown message fields are rejected before litellm.completion() is called."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match=match_str):
            p.respond(bad_msgs, tier="cheap")
        mod.completion.assert_not_called()


def test_large_unknown_field_never_reaches_provider():
    """A message with a large unknown field raises before provider invocation (canary absent)."""
    from core.providers.gcp.llm import LiteLLMProvider
    _CANARY_P10 = "CANARY_PASS10_FIELD_LEAK"
    p = LiteLLMProvider(_FULL_CFG)
    # 100 000-byte 'name' field — would silently bypass token estimation
    bad_msg = {"role": "user", "content": "hello", "name": "x" * 100_000}
    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = RuntimeError(f"boom {_CANARY_P10}")
        with pytest.raises(ValueError, match="unknown keys"):
            p.respond([bad_msg], tier="cheap")
        mod.completion.assert_not_called()
    # Canary must not appear in the raised exception
    # (provider was never invoked so there is nothing to chain, but verify anyway)


@pytest.mark.parametrize("bad_schema,match_str", [
    # Instance instead of class
    (object(), "must be a class"),
    # Built-in type that is not a CoreContractModel subclass
    (int,       "CoreContractModel"),
    (str,       "CoreContractModel"),
])
def test_invalid_response_schema_type_fails_before_provider(bad_schema, match_str):
    """Non-class or non-CoreContractModel response_schema raises before provider invocation."""
    from core.providers.gcp.llm import LiteLLMProvider
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match=match_str):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      response_schema=bad_schema)
        mod.completion.assert_not_called()


def test_plain_base_model_schema_fails_before_provider():
    """A plain pydantic.BaseModel (not CoreContractModel) raises before provider invocation."""
    from pydantic import BaseModel
    from core.providers.gcp.llm import LiteLLMProvider

    class _PlainModel(BaseModel):
        result: str

    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=None) as mod:
        with pytest.raises(ValueError, match="CoreContractModel"):
            p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                      response_schema=_PlainModel)
        mod.completion.assert_not_called()


def test_core_contract_model_schema_accepted():
    """A CoreContractModel subclass passes schema validation and reaches the provider."""
    from core.providers.gcp.llm import LiteLLMProvider
    import json as _json
    payload = {"value": "hello", "count": 1}
    resp = _mock_litellm_response(_json.dumps(payload), prompt_tokens=50, completion_tokens=20)
    p = LiteLLMProvider(_FULL_CFG)
    with _fake_litellm(completion_return=resp, completion_cost_return=0.001) as mod:
        result = p.respond([{"role": "user", "content": "hi"}], tier="cheap",
                           response_schema=_FakeSchema)
    mod.completion.assert_called_once()
    assert result.structured is not None
    assert isinstance(result.structured, _FakeSchema)


# ---------------------------------------------------------------------------
# Cycle 4 UI live-path hardening — bounded provider retry with honest cost
# ---------------------------------------------------------------------------

def test_provider_call_retries_once_and_combines_failed_attempt_usage():
    """One transient provider failure is retried, while failed-attempt cost remains in usage."""
    from core.providers.gcp.llm import LiteLLMProvider

    cfg = {
        **_FULL_CFG,
        "llm": {**_FULL_CFG["llm"], "provider_call_max_attempts": 2},
    }
    p = LiteLLMProvider(cfg)
    resp = _mock_litellm_response("ok", prompt_tokens=10, completion_tokens=20)

    with _fake_litellm(completion_return=resp, completion_cost_return=0.001) as mod:
        mod.completion.side_effect = [TimeoutError("transient"), resp]
        result = p.respond(
            [{"role": "user", "content": "hi"}],
            tier="cheap",
            params={"max_tokens": 7, "_authorized_prompt_tokens": 100},
        )

    assert mod.completion.call_count == 2
    assert result.text == "ok"
    # First attempt is conservative synthetic usage; second is real response usage.
    assert result.usage.prompt_tokens == 110
    assert result.usage.completion_tokens == 27
    assert result.usage.cost_native > 0.001
    assert result.usage.synthetic is True


def test_provider_call_all_attempts_fail_combines_conservative_usage():
    """If all retry attempts fail, BillableProviderError carries every attempted-call estimate."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError

    cfg = {
        **_FULL_CFG,
        "llm": {**_FULL_CFG["llm"], "provider_call_max_attempts": 2},
    }
    p = LiteLLMProvider(cfg)

    with _fake_litellm(completion_return=None) as mod:
        mod.completion.side_effect = TimeoutError("transient")
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond(
                [{"role": "user", "content": "hi"}],
                tier="cheap",
                params={"max_tokens": 7, "_authorized_prompt_tokens": 100},
            )

    err = exc_info.value
    assert mod.completion.call_count == 2
    assert err.category == "provider_call_failed"
    assert err.usage.prompt_tokens == 200
    assert err.usage.completion_tokens == 14
    assert err.usage.cost_native > 0
    assert err.usage.synthetic is True
    assert err.__cause__ is None
    assert err.__context__ is None


def test_provider_retry_usage_preserved_when_success_response_later_malformed():
    """Retry cost is still preserved if the successful attempt has a malformed response body."""
    from core.providers.gcp.llm import LiteLLMProvider
    from core.interfaces.errors import BillableProviderError

    cfg = {
        **_FULL_CFG,
        "llm": {**_FULL_CFG["llm"], "provider_call_max_attempts": 2},
    }
    p = LiteLLMProvider(cfg)
    resp = _mock_litellm_response("", prompt_tokens=10, completion_tokens=0)

    with _fake_litellm(completion_return=resp, completion_cost_return=0.001) as mod:
        mod.completion.side_effect = [TimeoutError("transient"), resp]
        with pytest.raises(BillableProviderError) as exc_info:
            p.respond(
                [{"role": "user", "content": "hi"}],
                tier="cheap",
                params={"max_tokens": 7, "_authorized_prompt_tokens": 100},
            )

    assert mod.completion.call_count == 2
    assert exc_info.value.category == "response_empty"
    assert exc_info.value.usage.prompt_tokens == 110
    assert exc_info.value.usage.completion_tokens == 7
    assert exc_info.value.usage.synthetic is True


def test_request_timeout_forwarded_to_litellm():
    """Configured request_timeout_s is forwarded as LiteLLM timeout."""
    from core.providers.gcp.llm import LiteLLMProvider

    cfg = {
        **_FULL_CFG,
        "llm": {**_FULL_CFG["llm"], "request_timeout_s": 123},
    }
    p = LiteLLMProvider(cfg)
    resp = _mock_litellm_response("ok", prompt_tokens=10, completion_tokens=20)

    with _fake_litellm(completion_return=resp, completion_cost_return=0.001) as mod:
        p.respond([{"role": "user", "content": "hi"}], tier="cheap")

    assert mod.completion.call_args.kwargs["timeout"] == 123.0


@pytest.mark.parametrize("bad_value", [0, -1, True, 1.5, "2"])
def test_provider_call_max_attempts_validation(bad_value):
    """Retry attempt count must be a positive non-bool integer."""
    from core.providers.gcp.llm import LiteLLMProvider

    cfg = {
        **_FULL_CFG,
        "llm": {**_FULL_CFG["llm"], "provider_call_max_attempts": bad_value},
    }
    with pytest.raises(ValueError, match="provider_call_max_attempts"):
        LiteLLMProvider(cfg)


@pytest.mark.parametrize("bad_value", [0, -1, False, float("nan"), float("inf"), "180"])
def test_request_timeout_validation(bad_value):
    """Request timeout must be positive, finite, and numeric."""
    from core.providers.gcp.llm import LiteLLMProvider

    cfg = {
        **_FULL_CFG,
        "llm": {**_FULL_CFG["llm"], "request_timeout_s": bad_value},
    }
    with pytest.raises(ValueError, match="request_timeout_s"):
        LiteLLMProvider(cfg)
