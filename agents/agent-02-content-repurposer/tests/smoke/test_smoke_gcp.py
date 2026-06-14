"""Live GCP/Vertex/LiteLLM structured-output smoke test for Agent 02 (merge gate).

This verifies the A1 contract end-to-end against a REAL model: the draft-generation stage asks
the shared ``LLMProvider`` for a structured ``LLMDraftBundle`` on the configured cheap/Flash
tier, deterministic validators run as guardrails, fallback is safe when a schema/provider hiccup
occurs, and legitimate quality-gate ``needs_human`` routing is distinguished from infrastructure
failure.

Skip behaviour
--------------
Unlike Agent 01's smoke (which relies on the offline CI excluding ``tests/smoke/`` by path), this
module **skips** when live prerequisites are absent (``litellm`` not installed OR ``VERTEX_AI_PROJECT``
unset) so the documented offline command ``pytest agents/agent-02-content-repurposer/tests`` stays
green locally. The live-smoke CI job sets the credentials, so the tests always run there.

Run live:
    # Windows PowerShell
    $env:PYTHONPATH = "packages;agents/agent-02-content-repurposer"
    $env:VERTEX_AI_PROJECT = "<your-gcp-project-id>"
    gcloud auth application-default login   # or set GOOGLE_APPLICATION_CREDENTIALS
    python -m pytest agents/agent-02-content-repurposer/tests/smoke -m smoke -x -v

    # bash
    PYTHONPATH="packages:agents/agent-02-content-repurposer" \
    VERTEX_AI_PROJECT="<your-gcp-project-id>" \
    python -m pytest agents/agent-02-content-repurposer/tests/smoke -m smoke -x -v
"""
from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path
from typing import Any

import pytest

from core.interfaces import LLMResponse
from core.interfaces.llm import LLMProvider, Tier
from core.interfaces.usage import Usage
from core.providers.mock.telemetry import StdoutTelemetry
from core.checks.no_cloud_sdk import scan

from agent.graph import build_graph
from agent.schemas import LLMDraftBundle, RepurposedContentPackage

pytestmark = [pytest.mark.smoke]

# --- live prerequisites -----------------------------------------------------------------------
_LITELLM_AVAILABLE = importlib.util.find_spec("litellm") is not None
_VERTEX_PROJECT_SET = bool(os.environ.get("VERTEX_AI_PROJECT", "").strip())

if not (_LITELLM_AVAILABLE and _VERTEX_PROJECT_SET):  # pragma: no cover - environment gate
    pytest.skip(
        "live GCP smoke requires litellm installed AND VERTEX_AI_PROJECT set "
        "(plus Application Default Credentials / GOOGLE_APPLICATION_CREDENTIALS). "
        f"litellm_available={_LITELLM_AVAILABLE}, vertex_project_set={_VERTEX_PROJECT_SET}.",
        allow_module_level=True,
    )

# Quality gate thresholds (mirror AGENT_SPEC / eval thresholds).
_MIN_OVERALL = 85
_MIN_FACTUAL = 90
_MIN_PLATFORM_FIT = 85
_MIN_USEFULNESS = 85
_MIN_CTA = 85
_COST_CEILING_INR = 30.0

_TARGET_PLATFORMS = ("linkedin", "instagram", "x_twitter", "short_video")
_AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"

# Realistic, fabrication-free source blog (no statistics/customer names to invent).
_SOURCE_BLOG = (
    "Most marketing teams treat a finished blog post as the end of the work, but the article is "
    "really the raw material for an entire campaign. The reason a single post underperforms across "
    "channels is that each platform rewards a different shape: a LinkedIn audience wants a clear "
    "professional point of view, an Instagram audience wants one visual idea they can grasp in a "
    "glance, an X audience wants a tight sequence of distinct thoughts, and a short-video viewer "
    "needs a hook in the first three seconds. A reliable repurposing workflow starts by isolating "
    "the single strongest idea in the source, naming the specific reader it helps, and stating why "
    "that reader should care. Only then does the team choose the format for each channel and adapt "
    "the angle, the proof, and the call to action without changing the meaning of the original "
    "piece. The goal is not more content but more mileage from content that was already worth "
    "publishing, with every draft kept review-ready so a human approves it before anything ships."
)


def _load_gcp_cfg() -> dict:
    """Load base.yaml deep-merged with gcp.yaml; disable output storage for a pure-LLM smoke."""
    import yaml

    root = Path(__file__).resolve().parents[2]
    base = yaml.safe_load((root / "config" / "base.yaml").read_text(encoding="utf-8"))
    gcp = yaml.safe_load((root / "config" / "gcp.yaml").read_text(encoding="utf-8"))

    def deep_merge(a: dict, b: dict) -> dict:
        result = dict(a)
        for k, v in b.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    cfg = deep_merge(base, gcp)
    # Keep the smoke focused on the LLM structured-output path and free of external writes;
    # object-storage live verification is a separate concern.
    cfg.setdefault("output_storage", {})["enabled"] = False
    return cfg


class _CapturingLLM(LLMProvider):
    """Wraps the real provider and records the structured LLMDraftBundle responses."""

    name = "capturing"

    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.bundles: list[LLMDraftBundle] = []
        self.usages: list[Usage] = []
        self.calls = 0
        self.structured_attempts = 0

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
        if response_schema is LLMDraftBundle:
            self.structured_attempts += 1
        response = self.inner.respond(
            messages, tier=tier, params=params, tools=tools, response_schema=response_schema
        )
        self.usages.append(response.usage)
        if response_schema is LLMDraftBundle and isinstance(response.structured, LLMDraftBundle):
            self.bundles.append(response.structured)
        return response


class _CapturingTelemetry(StdoutTelemetry):
    """Records every log event so the smoke can assert llm_drafts_used / fell_back were emitted."""

    def __init__(self, service: str) -> None:
        super().__init__(service=service)
        self.events: list[tuple[str, dict[str, Any]]] = []

    def log(self, msg: str, **fields: Any) -> None:
        self.events.append((msg, dict(fields)))
        super().log(msg, **fields)


@pytest.fixture(scope="module")
def _run() -> dict[str, Any]:
    """One paid end-to-end package run shared across all assertions (cost-frugal)."""
    from core.factory import get_llm_provider

    cfg = _load_gcp_cfg()
    real = get_llm_provider(cfg)
    llm = _CapturingLLM(real)
    tel = _CapturingTelemetry(service="agent02-smoke")
    graph = build_graph(cfg, llm, tel)
    package: RepurposedContentPackage = graph.invoke(
        {
            "raw_input": {
                "source_type": "raw_article_text",
                "title": "Turn one blog into a full multi-channel package",
                "summary": "A repurposing workflow that adapts one approved article per channel.",
                "full_text": _SOURCE_BLOG,
                "target_platforms": list(_TARGET_PLATFORMS),
                "audience": "B2B content marketing teams",
                "brand_tone": "clear, practical, confident",
                "campaign_goal": "turn one approved article into review-ready social drafts",
                "cta": "Read the full guide before you plan next week's content.",
            }
        }
    )["final_output"]
    return {"package": package, "llm": llm, "tel": tel, "provider_name": real.name}


def _gen_event(run: dict) -> dict | None:
    """The generate stage's own telemetry event (the one carrying the usage fields).

    The stage name is logged twice (the generic billable-call ".complete" carries only span_id),
    so select the event that has llm_drafts_used.
    """
    events = [
        f
        for (m, f) in run["tel"].events
        if m == "generate_platform_drafts.complete" and "llm_drafts_used" in f
    ]
    return events[0] if events else None


# --- System-correctness assertions (B) --------------------------------------------------------
# The live smoke verifies the live SYSTEM works against the real provider — not that a
# non-deterministic model produces flawless creative output on every run. The offline eval suite
# (deterministic scripted LLM) remains the strict proof of pass-quality behaviour.


def test_smoke_real_provider_is_litellm(_run) -> None:
    # The real model call goes through the shared LLMProvider/LiteLLM seam.
    assert _run["provider_name"] == "litellm"


def test_smoke_no_provider_crash(_run) -> None:
    # Provider hiccups are tolerated (best-effort/fallback); only a genuine deterministic bug yields
    # status 'error'. A live run must therefore reach a terminal status without an infra crash.
    assert _run["package"].status in {"pass", "needs_human"}
    assert _run["package"].status != "error", f"unexpected infra error: {_run['package'].notes!r}"


def test_smoke_real_provider_was_called(_run) -> None:
    # With credentials present, a live smoke must actually exercise the real provider path.
    assert _run["llm"].calls > 0
    assert _run["llm"].structured_attempts > 0
    assert any(
        usage.cost_native > 0 and not usage.synthetic for usage in _run["llm"].usages
    ), "no real non-synthetic provider usage was returned"


def test_smoke_structured_output_returned_or_fallback_handled(_run) -> None:
    # Either the real model returned a schema-valid LLMDraftBundle, or generation fell back safely.
    gen = _gen_event(_run)
    assert gen is not None, "generate llm-usage telemetry event missing"
    returned_bundle = bool(_run["llm"].bundles) and all(
        isinstance(b, LLMDraftBundle) for b in _run["llm"].bundles
    )
    fell_back = bool(gen.get("fell_back"))
    assert returned_bundle or fell_back, "neither a valid bundle nor a safe fallback occurred"
    if fell_back:
        assert _run["package"].platform_outputs, "fallback must still produce reviewable outputs"
        assert _run["package"].status != "error"


def test_smoke_telemetry_records_llm_usage_and_fallback(_run) -> None:
    # Telemetry records whether LLM drafts were used and whether fallback happened.
    gen = _gen_event(_run)
    assert gen is not None
    assert "llm_drafts_used" in gen and "fell_back" in gen


def test_smoke_deterministic_validators_ran(_run) -> None:
    # Deterministic validators run after generation (source of truth).
    package = _run["package"]
    assert package.validation_report, "platform validation report missing"
    assert package.factual_consistency_report is not None
    assert package.usefulness_report is not None
    assert package.quality_report is not None


def test_smoke_quality_semantics_respected(_run) -> None:
    # If the package passed, every gate threshold was met with zero hard-fails. If it was routed to
    # needs_human, that is a LEGITIMATE quality decision (a concrete hard-fail or sub-threshold) —
    # reported clearly, not treated as an infrastructure failure.
    package = _run["package"]
    q = package.quality_report
    assert q is not None
    if package.status == "pass":
        assert q.overall_score >= _MIN_OVERALL, f"overall {q.overall_score} < {_MIN_OVERALL}"
        assert package.factual_consistency_report.score >= _MIN_FACTUAL
        assert all(p.score >= _MIN_PLATFORM_FIT for p in q.platform_scores), q.platform_scores
        assert package.usefulness_report.score >= _MIN_USEFULNESS
        assert q.sub_scores.cta_quality * 10 >= _MIN_CTA
        assert not package.hard_fails, f"hard-fails on a passing package: {package.hard_fails}"
        assert {d.platform for d in package.platform_outputs} == set(_TARGET_PLATFORMS)
    else:
        assert package.status == "needs_human"
        assert package.hard_fails or not q.pass_flag, "needs_human without a concrete quality reason"
        print(
            "[smoke] routed to needs_human (legitimate quality issue, not infra): "
            f"hard_fails={[h.code for h in package.hard_fails]}, overall={q.overall_score}, "
            f"notes={package.notes!r}"
        )


def test_smoke_terminal_safety_respected(_run) -> None:
    # Terminal safety failures (injection / publishing / confidential / fake stats) never pass.
    package = _run["package"]
    terminal = [h.code for h in package.hard_fails if h.severity == "terminal"]
    if terminal:
        assert package.status == "needs_human", f"terminal hard-fails must escalate: {terminal}"
    if package.status == "pass":
        assert not package.hard_fails


def test_smoke_cost_billed_and_under_ceiling(_run) -> None:
    # Cost is real (non-zero) and strictly under the Rs.30/package ceiling.
    cost = _run["package"].cost.total_inr
    assert math.isfinite(cost)
    assert cost > 0.0, "real Vertex run must incur non-zero cost"
    assert cost < _COST_CEILING_INR, f"cost Rs{cost:.4f} >= ceiling Rs{_COST_CEILING_INR}"


def test_smoke_no_external_write(_run) -> None:
    # Review-only: no publishing / external write happened.
    assert _run["package"].output_package_uri is None


def test_smoke_agent_has_no_cloud_sdk_imports() -> None:
    assert scan(_AGENT_DIR) == []


def test_smoke_agent_has_no_external_action_clients() -> None:
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in _AGENT_DIR.rglob("*.py"))
    forbidden = (
        ".publish(",
        ".post(",
        ".schedule(",
        "cms",
        "crm",
        "facebook",
        "instagram graph api",
        "linkedin api",
        "twitter api",
        "mailchimp",
        "sendgrid",
        "requests.",
        "httpx.",
    )
    assert not any(token in text for token in forbidden)
