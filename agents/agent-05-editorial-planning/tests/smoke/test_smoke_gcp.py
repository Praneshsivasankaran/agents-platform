"""Live GCP / Vertex AI smoke test for Agent 05 - Editorial Planning Agent.

This is a CREDENTIALED, BILLED test. It is opt-in and skipped by default so the
offline suite (``pytest agents/agent-05-editorial-planning/tests``) stays green on
machines without GCP access.

How to run (PowerShell, from the repo root)
-------------------------------------------
::

    gcloud auth application-default login
    gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>

    $env:RUN_AGENT05_GCP_SMOKE = "1"
    $env:VERTEX_AI_PROJECT     = "<YOUR_PROJECT_ID>"
    $env:PYTHONPATH            = "packages;agents\\agent-05-editorial-planning"
    .\\.agent02-ui-venv\\Scripts\\python.exe -m pytest agents\\agent-05-editorial-planning\\tests\\smoke -q

Required environment when RUN_AGENT05_GCP_SMOKE=1
-------------------------------------------------
- ``RUN_AGENT05_GCP_SMOKE=1`` - opt-in gate. Without it every test here is SKIPPED.
- ``VERTEX_AI_PROJECT`` - your billing-enabled GCP project id. Resolved through the shared
  ``EnvSecretStore`` (``llm.vertex_project_secret`` in ``config/gcp.yaml``).
- Google Application Default Credentials, EITHER:
    * ``gcloud auth application-default login``, OR
    * ``GOOGLE_APPLICATION_CREDENTIALS=<path-to-service-account-json>``
- ``litellm`` + ``google-cloud-aiplatform`` installed in the venv (already in requirements.txt).
- The configured Vertex models must be available in the project:
  ``vertex_ai/gemini-2.5-flash`` (cheap) and ``vertex_ai/gemini-2.5-pro`` (strong).

``GCS_BUCKET`` is NOT required: the editorial-planning workflow and UI build only the LLM and
telemetry providers (no object storage). ``GCS_BUCKET`` is only needed if ``output_storage`` /
``object_storage`` is later enabled and exercised.

Fail-loud rule (never silently pass)
------------------------------------
If ``RUN_AGENT05_GCP_SMOKE=1`` is set but ``VERTEX_AI_PROJECT`` is missing, this module raises
at collection time with a clear setup message - it does NOT skip. GCP mode must never report
success without a configured project.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

_GATE = "RUN_AGENT05_GCP_SMOKE"
_PROJECT_ENV = "VERTEX_AI_PROJECT"

# Strict cost caps so a misconfigured model/pricing can never run away on a billed account.
_SMOKE_CALL_COST_CAP_INR = 10.0   # single LLM call
_SMOKE_RUN_COST_CAP_INR = 30.0    # full workflow run (matches cost.ceiling_inr in gcp.yaml)

# Gate FIRST, before any heavy import, so the default offline run skips cleanly and cheaply.
if not os.environ.get(_GATE):
    pytest.skip(
        f"Set {_GATE}=1 (plus {_PROJECT_ENV} and Google ADC) to run the credentialed "
        "Agent 05 GCP smoke test.",
        allow_module_level=True,
    )

# Gate is ON from here. A missing project must FAIL loudly at collection - never silently pass.
if not os.environ.get(_PROJECT_ENV):
    raise RuntimeError(
        f"{_GATE}=1 but {_PROJECT_ENV} is not set. Agent 05 GCP live mode cannot run without a "
        f"billing-enabled Vertex project. Set {_PROJECT_ENV}=<project-id> and provide Google ADC "
        "(`gcloud auth application-default login` or GOOGLE_APPLICATION_CREDENTIALS) before "
        "running the smoke test."
    )

_AGENT_ROOT = Path(__file__).resolve().parents[2]


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_gcp_cfg() -> dict:
    """Load ``config/base.yaml`` deep-merged with ``config/gcp.yaml`` (same merge the UI uses)."""
    import yaml

    base = yaml.safe_load((_AGENT_ROOT / "config" / "base.yaml").read_text(encoding="utf-8"))
    gcp = yaml.safe_load((_AGENT_ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))
    return _deep_merge(base, gcp)


@pytest.fixture(scope="module")
def cfg() -> dict:
    return _load_gcp_cfg()


def _llm(cfg: dict):
    """Build the LLM provider exactly the way agent service/UI does (factory + injected secrets)."""
    from core.factory import get_llm_provider

    return get_llm_provider(cfg)


def _sample_request() -> dict:
    return {
        "brand_name": "Northstar Wellness",
        "business_goal": "Drive qualified leads for a corporate wellness program",
        "target_audience": "HR leaders at mid-market companies",
        "campaign_theme": "Burnout prevention for distributed teams",
        "platforms": ["blog", "linkedin", "email"],
        "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
        "posting_frequency": {"cadence": "weekly", "count_per_week": 3},
        "brand_voice": "warm, expert, practical",
        "content_pillars": ["education", "proof", "conversion"],
        "existing_ideas": ["Checklist for spotting team burnout"],
        "constraints": ["Avoid medical diagnosis claims"],
    }


def test_smoke_gcp_config_forwarded(cfg: dict) -> None:
    """Config -> provider wiring: litellm Vertex provider with exact configured model/project/location.

    No network call - validates that ``AGENT05_UI_PROVIDER=gcp`` resolves to the real provider
    and forwards the configured values up to the API boundary.
    """
    import yaml

    raw_gcp = yaml.safe_load((_AGENT_ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))
    provider = _llm(cfg)

    assert provider.name == "litellm", f"expected litellm provider, got {provider.name!r}"
    assert provider._tier_models["cheap"] == raw_gcp["llm"]["tier_models"]["cheap"]
    assert provider._tier_models["strong"] == raw_gcp["llm"]["tier_models"]["strong"]
    assert provider._vertex_project, (
        f"{_PROJECT_ENV} must resolve to a non-empty Vertex project via EnvSecretStore"
    )
    assert provider._vertex_location == raw_gcp["llm"]["vertex_location"]


def test_smoke_gcp_text_response(cfg: dict) -> None:
    """Cheap tier: one real Vertex text completion with positive, finite, capped cost."""
    from core.cost import usage_cost_inr

    provider = _llm(cfg)
    # Gemini 2.5 Flash spends reasoning tokens against max_tokens; leave headroom for output.
    result = provider.respond(
        [{"role": "user", "content": "Reply with exactly: OK"}],
        tier="cheap",
        params={"max_tokens": 128},
    )
    assert result.text, "expected non-empty text from Vertex"
    assert result.usage.prompt_tokens > 0, "real call must account prompt tokens"
    assert result.usage.completion_tokens > 0, "real call must have output tokens"
    assert result.usage.cost_native > 0 and math.isfinite(result.usage.cost_native)
    assert result.usage.currency == "USD", "LiteLLM reports cost in USD"

    cost_inr = usage_cost_inr(result.usage, fx_rates=cfg["cost"]["fx_rates"])
    assert math.isfinite(cost_inr) and cost_inr > 0
    assert cost_inr < _SMOKE_CALL_COST_CAP_INR, f"cost Rs{cost_inr:.4f} >= cap Rs{_SMOKE_CALL_COST_CAP_INR}"


def test_smoke_gcp_structured_response(cfg: dict) -> None:
    """Cheap tier: one real structured Vertex response validated against a CoreContractModel."""
    from pydantic import Field

    from core.cost import usage_cost_inr
    from core.interfaces.base import CoreContractModel

    class _Plan(CoreContractModel):
        headline: str = Field(min_length=1)
        audience: str = Field(min_length=1)

    provider = _llm(cfg)
    result = provider.respond(
        [{"role": "user", "content": "Return a one-line content headline and its target audience."}],
        tier="cheap",
        response_schema=_Plan,
        params={"max_tokens": 256},
    )
    assert result.structured is not None
    assert isinstance(result.structured, _Plan)
    assert result.structured.headline and result.structured.audience
    assert result.usage.cost_native > 0 and math.isfinite(result.usage.cost_native)
    assert result.usage.currency == "USD"

    cost_inr = usage_cost_inr(result.usage, fx_rates=cfg["cost"]["fx_rates"])
    assert math.isfinite(cost_inr) and cost_inr > 0
    assert cost_inr < _SMOKE_CALL_COST_CAP_INR, f"cost Rs{cost_inr:.4f} >= cap Rs{_SMOKE_CALL_COST_CAP_INR}"


def test_smoke_gcp_full_workflow(cfg: dict) -> None:
    """End-to-end editorial planning in GCP mode - the exact provider path the UI uses.

    Builds the graph from the GCP-merged config with the live LLM + telemetry providers (object
    storage is intentionally not constructed - the UI does the same), runs a real plan, and asserts
    a valid package produced from live Vertex output within the run cost cap.
    """
    from core.factory import get_llm_provider, get_telemetry

    from agent.schemas import EditorialPlanningPackage
    from agent.workflow import build_graph

    graph = build_graph(cfg, get_llm_provider(cfg), get_telemetry(cfg))
    package = graph.invoke({"raw_input": _sample_request()})["final_output"]

    assert isinstance(package, EditorialPlanningPackage)
    assert package.status in {"pass", "needs_human"}, f"unexpected status {package.status!r}: {package.notes}"
    assert package.generation_used_llm is True, "live GCP run must use real LLM output, not only fallbacks"
    assert package.editorial_calendar, "expected a non-empty editorial calendar"
    assert package.content_briefs, "expected non-empty content briefs"
    assert package.cost.total_inr > 0, "real Vertex calls must record positive INR cost"
    assert package.cost.total_inr < _SMOKE_RUN_COST_CAP_INR, (
        f"run cost Rs{package.cost.total_inr:.4f} >= cap Rs{_SMOKE_RUN_COST_CAP_INR}"
    )
