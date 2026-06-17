"""GCP / Vertex AI smoke pattern for Agent 20."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from core.factory import get_llm_provider, get_object_storage


_AGENT_ROOT = Path(__file__).resolve().parents[2]
_SMOKE_RUN_COST_CAP_INR = 50.0
_SAMPLE_REQUEST = {
    "conversion_goal": "Increase demo request submissions",
    "target_audience": "RevOps leaders",
    "page_notes": "Users drop near the proof and pricing section.",
    "metric_summary": "Visitors 1000, form starts 120, submissions 45.",
    "funnel_stages": [
        {"stage": "Visitors", "count": 1000},
        {"stage": "Form starts", "count": 120},
        {"stage": "Submissions", "count": 45},
    ],
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _gcp_cfg() -> dict:
    base = yaml.safe_load((_AGENT_ROOT / "config" / "base.yaml").read_text(encoding="utf-8"))
    gcp = yaml.safe_load((_AGENT_ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))
    return _deep_merge(base, gcp)


class _StubSecretStore:
    def get(self, key: str) -> str:
        return f"smoke-{key.lower()}"


def test_gcp_overlay_constructs_providers_offline() -> None:
    cfg = _gcp_cfg()
    raw_gcp = yaml.safe_load((_AGENT_ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))
    stub = _StubSecretStore()
    llm = get_llm_provider(cfg, secret_store=stub)
    assert llm.name == "litellm"
    assert llm._tier_models["cheap"] == raw_gcp["llm"]["tier_models"]["cheap"]
    assert llm._tier_models["strong"] == raw_gcp["llm"]["tier_models"]["strong"]
    assert llm._vertex_location == raw_gcp["llm"]["vertex_location"]
    assert llm._vertex_project
    assert type(get_object_storage(cfg, secret_store=stub)).__name__ == "GCSObjectStorage"
    assert 0 < float(cfg["cost"]["ceiling_inr"]) <= 50.0


@pytest.mark.smoke
@pytest.mark.skipif(
    not (os.environ.get("RUN_DIGITAL_MARKETING_GCP_SMOKE") and os.environ.get("VERTEX_AI_PROJECT")),
    reason="Set RUN_DIGITAL_MARKETING_GCP_SMOKE=1 + VERTEX_AI_PROJECT + Google ADC to run the live GCP smoke.",
)
def test_gcp_live_full_workflow() -> None:
    from core.factory import get_telemetry
    from agent.schemas import AgentPackage
    from agent.workflow import build_graph

    cfg = _gcp_cfg()
    graph = build_graph(cfg, get_llm_provider(cfg), get_telemetry(cfg))
    package = graph.invoke({"raw_input": _SAMPLE_REQUEST})["final_output"]
    assert isinstance(package, AgentPackage)
    assert package.status in {"pass", "needs_human", "stopped_cost_ceiling", "error"}
    assert package.cost_usage.total_inr <= _SMOKE_RUN_COST_CAP_INR
