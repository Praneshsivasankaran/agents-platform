"""GCP / Vertex AI smoke pattern for this Demand Generation agent.

Two layers, mirroring Agents 01-07 but lighter:

1. ``test_gcp_overlay_constructs_providers_offline`` — runs in NORMAL CI with NO
   credentials and NO network. It deep-merges ``base.yaml`` + ``gcp.yaml`` and
   constructs the real ``LiteLLMProvider`` + ``GCSObjectStorage`` through the
   factory. The LiteLLM / Vertex / GCS SDKs are imported lazily inside the call
   paths (``respond`` / ``put``), which this test never invokes — so it proves
   the config overlay is wired correctly without billing or auth.

2. ``test_gcp_live_full_workflow`` — OPT-IN, CREDENTIALED, BILLED. Skipped by
   default; set ``RUN_DEMAND_GEN_GCP_SMOKE=1`` + ``VERTEX_AI_PROJECT`` + Google
   ADC to exercise the real Vertex path end-to-end.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from core.factory import get_llm_provider, get_object_storage


_AGENT_ROOT = Path(__file__).resolve().parents[2]
_SMOKE_RUN_COST_CAP_INR = 50.0

# A benign, planning-only request that satisfies every Demand Generation agent's
# required fields without tripping any hard-fail rule (no protected attributes,
# forbidden actions, PII, or audience-size estimation).
_SAMPLE_REQUEST = {
    "business_context": "B2B SaaS workflow automation for revenue operations teams.",
    "product_or_service": "Revenue workflow automation",
    "icp_summary": "Mid-market and enterprise SaaS companies with RevOps ownership.",
    "segment_summary": "RevOps-led accounts with growing SDR teams and documented funnel leakage.",
    "campaign_goal": "Plan a pipeline generation program for next quarter.",
    "offer": "Lead handoff maturity benchmark assessment",
    "budget": "INR 10 lakh planning budget, not approved spend",
    "source_notes": "Best customers have complex multi-step lead handoffs and RevOps ownership.",
    "constraints": ["Planning guidance only", "Human review before launch", "No protected-attribute targeting"],
    "audience_fields": ["Company size tier", "CRM maturity", "Region"],
    "signals": ["ICP fit: company size", "Engagement: demo page visit", "Intent: pricing page visit"],
    "score_bands": ["Hot: 80-100", "Warm: 50-79", "Cold: below 50"],
    "content_inventory": ["Benchmark report", "Case study", "ROI worksheet"],
    "funnel_stages": [
        {"stage": "Visitors", "count": 1000},
        {"stage": "Leads", "count": 120},
        {"stage": "Opportunities", "count": 20},
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
    """Returns a deterministic dummy value for any key — no real credentials."""

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
    assert llm._vertex_project  # resolved via SecretStore (stubbed)

    storage = get_object_storage(cfg, secret_store=stub)
    assert type(storage).__name__ == "GCSObjectStorage"

    # Per-agent ceiling must honor the platform Rs.50 cap.
    assert 0 < float(cfg["cost"]["ceiling_inr"]) <= 50.0


@pytest.mark.smoke
@pytest.mark.skipif(
    not (os.environ.get("RUN_DEMAND_GEN_GCP_SMOKE") and os.environ.get("VERTEX_AI_PROJECT")),
    reason="Set RUN_DEMAND_GEN_GCP_SMOKE=1 + VERTEX_AI_PROJECT + Google ADC to run the live GCP smoke.",
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
