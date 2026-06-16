"""Live GCP/Vertex/LiteLLM smoke test for Agent 04.

This is a paid live smoke and should be run only when intentionally testing
GCP. It skips at import time when live prerequisites are absent so ordinary
offline test commands stay green.

Run live from the repository root:

    $env:PYTHONPATH = "packages;agents/agent-04-seo-optimizer"
    $env:VERTEX_AI_PROJECT = "<your-gcp-project-id>"
    gcloud auth application-default login
    python -m pytest agents/agent-04-seo-optimizer/tests/smoke -m smoke -x -v
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
from pathlib import Path
from typing import Any

import pytest


_AGENT_ROOT = Path(__file__).resolve().parents[2]
_AGENT_DIR = _AGENT_ROOT / "agent"
sys.path = [
    item
    for item in sys.path
    if item and str(Path(item).resolve()) != str(_AGENT_ROOT.resolve())
]
sys.path.insert(0, str(_AGENT_ROOT))
for module_name in [name for name in sys.modules if name == "agent" or name.startswith("agent.")]:
    sys.modules.pop(module_name, None)

from core.checks.no_cloud_sdk import scan
from core.interfaces import LLMResponse
from core.interfaces.llm import LLMProvider, Tier
from core.interfaces.usage import Usage
from core.providers.mock.telemetry import StdoutTelemetry

from agent.graph import build_graph
from agent.schemas import (
    FAQBundle,
    HeadingPlan,
    MetadataPackage,
    OptimizedDraftPackage,
    ReadabilityReport,
    SEOOptimizationPackage,
)


_LITELLM_AVAILABLE = importlib.util.find_spec("litellm") is not None
_VERTEX_PROJECT_SET = bool(os.environ.get("VERTEX_AI_PROJECT", "").strip())
_LIVE_SKIP_REASON = (
    "live GCP smoke requires litellm installed AND VERTEX_AI_PROJECT set "
    "(plus Application Default Credentials / GOOGLE_APPLICATION_CREDENTIALS). "
    f"litellm_available={_LITELLM_AVAILABLE}, vertex_project_set={_VERTEX_PROJECT_SET}."
)

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not (_LITELLM_AVAILABLE and _VERTEX_PROJECT_SET), reason=_LIVE_SKIP_REASON),
]


_COST_CEILING_INR = 20.0
_STRUCTURED_SCHEMAS = (
    MetadataPackage,
    HeadingPlan,
    ReadabilityReport,
    FAQBundle,
    OptimizedDraftPackage,
)

_SOURCE_DRAFT = (
    "Cloud neutral AI agents help engineering and marketing teams avoid platform lock in. "
    "A reusable agent platform keeps the workflow logic separate from the cloud provider, "
    "so the same agent can run with Vertex AI today and another provider later. The practical "
    "pattern is to put model calls behind an LLM provider, keep schemas strict, route costs "
    "through a shared ledger, and expose every result as a review package. This helps teams "
    "test locally, run a live provider smoke test, and keep humans responsible for final "
    "approval. A good starting point is one repeatable content workflow where the source "
    "draft already exists and the agent only improves structure, metadata, headings, keyword "
    "placement, readability, and review notes."
)


def _load_gcp_cfg() -> dict[str, Any]:
    import yaml

    base = yaml.safe_load((_AGENT_ROOT / "config" / "base.yaml").read_text(encoding="utf-8"))
    gcp = yaml.safe_load((_AGENT_ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))

    def deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        result = dict(a)
        for key, value in b.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    cfg = deep_merge(base, gcp)
    cfg.setdefault("output_storage", {})["enabled"] = False
    return cfg


class _CapturingLLM(LLMProvider):
    name = "capturing"

    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.calls = 0
        self.structured_attempts = 0
        self.usages: list[Usage] = []
        self.structured_payloads: list[object] = []

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        self.calls += 1
        if response_schema in _STRUCTURED_SCHEMAS:
            self.structured_attempts += 1
        response = self.inner.respond(
            messages,
            tier=tier,
            params=params,
            tools=tools,
            response_schema=response_schema,
        )
        self.usages.append(response.usage)
        if response.structured is not None:
            self.structured_payloads.append(response.structured)
        return response


@pytest.fixture(scope="module")
def _run() -> dict[str, Any]:
    from core.factory import get_llm_provider

    cfg = _load_gcp_cfg()
    real_llm = get_llm_provider(cfg)
    llm = _CapturingLLM(real_llm)
    telemetry = StdoutTelemetry(service="agent04-smoke")
    graph = build_graph(cfg, llm, telemetry)
    package: SEOOptimizationPackage = graph.invoke(
        {
            "raw_input": {
                "draft_content": _SOURCE_DRAFT,
                "topic": "Cloud neutral AI agents",
                "primary_keyword": "cloud neutral AI agents",
                "secondary_keywords": (
                    "agent platform",
                    "provider abstraction",
                    "SEO workflow",
                ),
                "target_audience": "engineering and marketing leaders",
                "content_goal": "educate readers on a safe reusable agent workflow",
                "brand_tone": "clear, practical, confident",
                "cta_direction": "Ask for a platform review",
                "constraints": ("Do not invent statistics.", "Keep review-only boundaries clear."),
            }
        }
    )["final_output"]
    return {"package": package, "llm": llm, "provider_name": real_llm.name}


def test_smoke_real_provider_is_litellm(_run) -> None:
    assert _run["provider_name"] == "litellm"


def test_smoke_reaches_terminal_package(_run) -> None:
    package = _run["package"]
    assert isinstance(package, SEOOptimizationPackage)
    assert package.status in {"pass", "needs_human"}
    assert package.status != "error", package.notes
    assert package.title_options
    assert package.meta_description
    assert package.url_slug
    assert package.optimized_draft


def test_smoke_real_provider_was_called(_run) -> None:
    llm = _run["llm"]
    assert llm.calls > 0
    assert llm.structured_attempts > 0
    assert any(usage.cost_native > 0 and not usage.synthetic for usage in llm.usages)


def test_smoke_cost_under_ceiling(_run) -> None:
    cost = _run["package"].cost.total_inr
    assert math.isfinite(cost)
    assert 0.0 < cost < _COST_CEILING_INR


def test_smoke_quality_semantics_respected(_run) -> None:
    package = _run["package"]
    assert package.seo_score is not None
    if package.status == "pass":
        assert package.seo_score.passed
        assert package.pass_status == "pass"
        assert package.seo_score.total_score >= 80
        assert not package.seo_score.hard_fail_codes
    else:
        assert package.status == "needs_human"
        assert not package.seo_score.passed or package.seo_score.hard_fail_codes


def test_smoke_review_only_no_external_output_uri(_run) -> None:
    package = _run["package"]
    assert package.notes
    assert "external action" in package.notes.lower() or package.status == "needs_human"


def test_smoke_agent_has_no_cloud_sdk_imports() -> None:
    assert scan(_AGENT_DIR) == []
