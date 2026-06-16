"""Live GCP / Vertex AI smoke test for Agent 07 - Case Study Generation Agent.

This is a CREDENTIALED, BILLED test. It is opt-in and skipped by default so the
offline suite stays green on machines without GCP access.

PowerShell, from the repo root:

    gcloud auth application-default login
    gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>

    $env:RUN_AGENT07_GCP_SMOKE = "1"
    $env:VERTEX_AI_PROJECT     = "<YOUR_PROJECT_ID>"
    $env:PYTHONPATH            = "packages;agents\\agent-07-case-study-generation"
    .\\.agent02-ui-venv\\Scripts\\python.exe -m pytest agents\\agent-07-case-study-generation\\tests\\smoke -q

The workflow itself does not require GCS for v1; only the LLM provider is exercised.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import pytest


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not os.environ.get("RUN_AGENT07_GCP_SMOKE"),
        reason="Set RUN_AGENT07_GCP_SMOKE=1 plus VERTEX_AI_PROJECT and Google ADC to run Agent 07 GCP smoke.",
    ),
    pytest.mark.skipif(
        not os.environ.get("VERTEX_AI_PROJECT"),
        reason="VERTEX_AI_PROJECT is required for Agent 07 GCP smoke.",
    ),
]

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_SMOKE_CALL_COST_CAP_INR = 10.0
_SMOKE_RUN_COST_CAP_INR = 25.0


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
        "customer_name": "Acme Bank",
        "industry": "Financial services",
        "target_audience": "CIOs and operations leaders",
        "challenge": "Manual onboarding reviews delayed enterprise account launches and scattered approval evidence.",
        "solution_summary": "A workflow automation program centralized onboarding tasks, approval routing, and evidence capture.",
        "product_or_service": "LaunchFlow onboarding automation",
        "implementation_notes": "The rollout started with one business unit, mapped approval steps, and trained operations managers.",
        "results": "Enterprise account launch time decreased and operations teams gained a clearer audit trail.",
        "metrics": [
            {
                "label": "Launch cycle reduction",
                "value": "32%",
                "baseline": "Average launch cycle before rollout",
                "after": "Average launch cycle after rollout",
                "source": "Internal implementation report",
            }
        ],
        "customer_quotes": ["The workflow gave our operations leads one place to manage launch evidence."],
        "source_notes": "Internal implementation report and customer interview notes.",
        "tone": "executive",
        "cta_goal": "Book an onboarding workflow assessment",
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

    from agent.schemas import CaseStudyPackage
    from agent.workflow import build_graph

    graph = build_graph(cfg, get_llm_provider(cfg), get_telemetry(cfg))
    package = graph.invoke({"raw_input": _sample_request()})["final_output"]

    assert isinstance(package, CaseStudyPackage)
    assert package.status in {"approve", "revise", "reject"}
    assert package.final_markdown_draft
    assert package.generation_used_llm is True
    assert package.cost_usage.total_inr > 0
    assert package.cost_usage.total_inr < _SMOKE_RUN_COST_CAP_INR
