"""Live GCP / Vertex AI smoke test for Agent 06 - Whitepaper Development Agent.

This is a CREDENTIALED, BILLED test. It is opt-in and skipped by default so the
offline suite stays green on machines without GCP access.

PowerShell, from the repo root:

    gcloud auth application-default login
    gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>

    $env:RUN_AGENT06_GCP_SMOKE = "1"
    $env:VERTEX_AI_PROJECT     = "<YOUR_PROJECT_ID>"
    $env:PYTHONPATH            = "packages;agents\\agent-06-whitepaper-development"
    .\\.agent02-ui-venv\\Scripts\\python.exe -m pytest agents\\agent-06-whitepaper-development\\tests\\smoke -q

The workflow itself does not require GCS for v1; only the LLM provider is exercised.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

_GATE = "RUN_AGENT06_GCP_SMOKE"
_PROJECT_ENV = "VERTEX_AI_PROJECT"
_SMOKE_CALL_COST_CAP_INR = 10.0
_SMOKE_RUN_COST_CAP_INR = 50.0

if not os.environ.get(_GATE):
    pytest.skip(
        f"Set {_GATE}=1 (plus {_PROJECT_ENV} and Google ADC) to run the credentialed "
        "Agent 06 GCP smoke test.",
        allow_module_level=True,
    )

if not os.environ.get(_PROJECT_ENV):
    raise RuntimeError(
        f"{_GATE}=1 but {_PROJECT_ENV} is not set. Agent 06 GCP live mode cannot run without "
        "a billing-enabled Vertex project."
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
    import yaml

    base = yaml.safe_load((_AGENT_ROOT / "config" / "base.yaml").read_text(encoding="utf-8"))
    gcp = yaml.safe_load((_AGENT_ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))
    return _deep_merge(base, gcp)


@pytest.fixture(scope="module")
def cfg() -> dict:
    return _load_gcp_cfg()


def _llm(cfg: dict):
    from core.factory import get_llm_provider

    return get_llm_provider(cfg)


def _sample_request() -> dict:
    return {
        "topic": "AI governance operating model",
        "company_context": "Acme PolicyOS helps compliance teams manage AI policy reviews.",
        "target_audience": "CIOs and compliance leaders",
        "industry": "Financial services",
        "problem": "AI initiatives are slowed by manual policy review and unclear ownership.",
        "solution": "A workflow platform for AI policy intake, review routing, evidence capture, and approval tracking.",
        "tone": "executive, precise, and practical",
        "target_depth": "detailed B2B whitepaper package",
        "cta": "Book a governance readiness workshop",
        "proof_points": ["Internal pilot centralized review evidence across three policy teams"],
        "source_notes": ["Internal product brief approved by compliance SME"],
        "differentiators": ["role-based review routing", "evidence capture"],
        "objections": ["Buyers may worry about adoption effort"],
        "compliance_constraints": ["Avoid legal advice claims"],
    }


def test_smoke_gcp_config_forwarded(cfg: dict) -> None:
    import yaml

    raw_gcp = yaml.safe_load((_AGENT_ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))
    provider = _llm(cfg)

    assert provider.name == "litellm"
    assert provider._tier_models["cheap"] == raw_gcp["llm"]["tier_models"]["cheap"]
    assert provider._tier_models["strong"] == raw_gcp["llm"]["tier_models"]["strong"]
    assert provider._vertex_project
    assert provider._vertex_location == raw_gcp["llm"]["vertex_location"]


def test_smoke_gcp_text_response(cfg: dict) -> None:
    from core.cost import usage_cost_inr

    provider = _llm(cfg)
    result = provider.respond(
        [{"role": "user", "content": "Reply with exactly: OK"}],
        tier="cheap",
        params={"max_tokens": 128},
    )
    assert result.text
    assert result.usage.prompt_tokens > 0
    assert result.usage.completion_tokens > 0
    assert result.usage.cost_native > 0 and math.isfinite(result.usage.cost_native)
    assert result.usage.currency == "USD"

    cost_inr = usage_cost_inr(result.usage, fx_rates=cfg["cost"]["fx_rates"])
    assert math.isfinite(cost_inr) and cost_inr > 0
    assert cost_inr < _SMOKE_CALL_COST_CAP_INR


def test_smoke_gcp_full_workflow(cfg: dict) -> None:
    from core.factory import get_llm_provider, get_telemetry

    from agent.schemas import WhitepaperDevelopmentPackage
    from agent.workflow import build_graph

    graph = build_graph(cfg, get_llm_provider(cfg), get_telemetry(cfg))
    package = graph.invoke({"raw_input": _sample_request()})["final_output"]

    assert isinstance(package, WhitepaperDevelopmentPackage)
    assert package.status in {"pass", "needs_human", "needs_review_budget_limited"}
    assert package.executive_summary
    assert package.key_claims
    assert package.generation_used_llm is True
    assert package.cost.total_inr > 0
    assert package.cost.total_inr < _SMOKE_RUN_COST_CAP_INR
