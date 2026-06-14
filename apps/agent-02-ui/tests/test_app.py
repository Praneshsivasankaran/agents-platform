from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _load_app_module():
    spec = importlib.util.spec_from_file_location("agent02_ui_app_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ui(tmp_path, monkeypatch):
    module = _load_app_module()
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    module.RUNS_DIR.mkdir()
    return module


@pytest.fixture()
def client(ui):
    return TestClient(ui.app)


class _FakeGraph:
    def __init__(self, package: Any) -> None:
        self.package = package

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert "raw_input" in payload
        return {"final_output": self.package}


def _valid_form(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "source_type": "raw_article_text",
        "title": "Turn one blog into a channel-native campaign",
        "summary": "A source article about repurposing approved long-form content.",
        "full_text": (
            "Content teams often invest heavily in long-form articles, but that work loses "
            "value when it is copied unchanged into every channel. A stronger repurposing "
            "workflow preserves the source meaning, identifies the audience value, and reshapes "
            "the format for each platform. LinkedIn needs a professional point of view, "
            "Instagram needs a visual idea, X needs a tight thread, and short video needs a "
            "clear hook with scene direction. The goal is review-ready content that a human can "
            "inspect before anything is published."
        ),
        "audience": "B2B content marketing teams",
        "brand_tone": "clear, practical, confident",
        "campaign_goal": "turn one approved article into review-ready social drafts",
        "cta": "Read the full guide before planning next week's content.",
        "target_platforms": ["linkedin", "instagram", "x_twitter", "short_video"],
    }
    data.update(overrides)
    return data


def _fake_package(ui, *, status: str = "needs_more_input"):
    return ui.RepurposedContentPackage(
        status=status,
        source_summary="A source article about adapting one blog for multiple channels.",
        content_brief="Preserve source meaning while adapting format per platform.",
        cost=ui.CostUsage(stage_costs=(), total_inr=0.0),
        notes="Fake live graph package for UI tests.",
    )


def _needs_human_display_package(ui):
    from agent.schemas import HardFail, HashtagSet, PlatformDraft

    return ui.RepurposedContentPackage(
        status="needs_human",
        source_summary="A source article about adapting approved content for multiple channels.",
        content_brief="Use channel-native drafts while preserving the source meaning.",
        platform_outputs=(
            PlatformDraft(
                platform="linkedin",
                content_type="post",
                hook="LinkedIn duplicated hook sentence.",
                body="LinkedIn duplicated hook sentence.\n\nThe body carries the useful detail.",
                cta="Review the source before posting manually.",
                why_this_works="It gives a professional reader a clear reason to review.",
                audience_value="Marketing teams get a grounded next step.",
                quality_score=80,
            ),
            PlatformDraft(
                platform="instagram",
                content_type="caption",
                hook="Instagram duplicated hook sentence.",
                body="Instagram duplicated hook sentence.\n\nThe caption adds the visual angle.",
                cta="Review the source before posting manually.",
                visual_angle="Carousel showing source to draft transformation.",
                why_this_works="It gives a visual channel a clear angle.",
                audience_value="Marketing teams get a grounded next step.",
                quality_score=80,
            ),
            PlatformDraft(
                platform="x_twitter",
                content_type="thread",
                hook="Thread opening about async docs.",
                body="1/5 Thread opening about async docs.\n2/5 Map the source claim before drafting.",
                thread_posts=(
                    "1/5 1/5 Thread opening about async docs.",
                    "2/5 Map the source claim before drafting.",
                    "2/5 Map the source claim before drafting.",
                ),
                cta="Review the source before posting manually.",
                why_this_works="It turns a source into a concise sequence.",
                audience_value="Marketing teams get a grounded next step.",
                quality_score=80,
            ),
            PlatformDraft(
                platform="short_video",
                content_type="script",
                hook="Turn the approved source into a quick script.",
                body="A short-video script for human review.",
                cta="Review the source before posting manually.",
                hashtags=("#shortvideo", "#shouldhide"),
                scene_directions=("0-3s: show the source title.", "4-30s: show the core claim."),
                voiceover="Turn one approved source into a review-ready short-video script.",
                on_screen_text=("Approved source", "Core claim"),
                why_this_works="It includes scene direction, voiceover, and review context.",
                audience_value="Marketing teams get a grounded next step.",
                quality_score=80,
            ),
        ),
        hashtag_sets=(
            HashtagSet(platform="linkedin", hashtags=("#content",)),
            HashtagSet(platform="short_video", hashtags=("#shortvideo", "#shouldhide")),
        ),
        cost=ui.CostUsage(stage_costs=(), total_inr=0.0),
        hard_fails=(
            HardFail(code="generic_content", severity="retriable", reason="Generic content detected."),
            HardFail(
                code="platform_mismatch",
                severity="retriable",
                reason="Platform validation failed.",
                platform="x_twitter",
            ),
        ),
        improvement_suggestions=("Replace generic phrasing with source-specific value.",),
    )


def _install_fake_live_graph(ui, monkeypatch, *, status: str = "needs_more_input") -> None:
    monkeypatch.setenv("VERTEX_AI_PROJECT", "agents-platform-1212")

    def _fake_build_graph_from_config(cfg: dict[str, Any], provider_mode: str):
        assert provider_mode == "gcp"
        assert cfg["llm"]["provider"] == "litellm"
        telemetry = ui.CapturingTelemetry(ui.get_telemetry(ui.load_agent_config("gcp")))
        return _FakeGraph(_fake_package(ui, status=status)), telemetry

    monkeypatch.setattr(ui, "_build_graph_from_config", _fake_build_graph_from_config)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_form_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Generate Package" in response.text
    assert "GCP/Vertex live" in response.text
    assert "mock mode" not in response.text
    assert "AGENT02_UI_PROVIDER" not in response.text
    assert "Provider mode" not in response.text
    assert "Raw article text" in response.text
    assert "Agent 01 blog package" in response.text
    assert "Newsletter/email" in response.text
    assert "repurposing_brief_from_agent_03" in response.text
    assert "Generating with live GCP/Vertex. This may take a few minutes." in response.text
    assert "Generating..." in response.text


def test_home_warns_when_live_config_missing(client, monkeypatch):
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    response = client.get("/")

    assert response.status_code == 200
    assert "Live GCP/Vertex configuration is missing" in response.text
    assert "VERTEX_AI_PROJECT" in response.text
    assert "Google ADC" in response.text
    assert "mock" not in response.text.lower()


def test_post_valid_live_config_input_creates_run_json_and_redirects(client, ui, monkeypatch):
    _install_fake_live_graph(ui, monkeypatch)
    response = client.post("/runs", data=_valid_form(), follow_redirects=False)

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["provider_mode"] == "gcp"
    assert record["source_type"] == "raw_article_text"
    assert record["input"]["target_platforms"] == ["linkedin", "instagram", "x_twitter", "short_video"]
    assert record["package"]["status"] == "needs_more_input"
    assert (ui.RUNS_DIR / f"{run_id}.json").exists()


def test_post_valid_newsletter_input_includes_newsletter(client, ui, monkeypatch):
    _install_fake_live_graph(ui, monkeypatch)
    response = client.post(
        "/runs",
        data=_valid_form(include_newsletter="1"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert "newsletter" in record["input"]["target_platforms"]
    assert record["input"]["include_newsletter"] is True


def test_post_valid_agent03_brief_json_is_included(client, ui, monkeypatch):
    _install_fake_live_graph(ui, monkeypatch)
    response = client.post(
        "/runs",
        data=_valid_form(
            repurposing_brief_from_agent_03=(
                '{"core_campaign_message":"Keep the campaign consistent.",'
                '"platform_recommendations":["linkedin","newsletter"],'
                '"message_guardrails":["Do not invent benchmarks."]}'
            )
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    brief = record["input"]["repurposing_brief_from_agent_03"]
    assert brief["core_campaign_message"] == "Keep the campaign consistent."
    assert brief["platform_recommendations"] == ["linkedin", "newsletter"]


def test_post_missing_required_input_creates_safe_error_result(client, ui, monkeypatch):
    _install_fake_live_graph(ui, monkeypatch)
    response = client.post(
        "/runs",
        data=_valid_form(title="  "),
        follow_redirects=False,
    )

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "Title is required" in record["package"]["notes"]


def test_post_invalid_agent03_brief_json_creates_safe_error_result(client, ui, monkeypatch):
    _install_fake_live_graph(ui, monkeypatch)
    response = client.post(
        "/runs",
        data=_valid_form(repurposing_brief_from_agent_03="{not-json"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "Agent 03 repurposing brief must be valid JSON" in record["package"]["notes"]


def test_missing_live_config_returns_safe_error(client, ui, monkeypatch):
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    response = client.post("/runs", data=_valid_form(), follow_redirects=False)

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    notes = record["package"]["notes"]
    assert record["package"]["status"] == "error"
    assert "Live GCP/Vertex configuration is missing" in notes
    assert "VERTEX_AI_PROJECT" in notes
    assert "Google ADC" in notes
    assert "credential" not in notes.lower()


def test_result_page_renders_run_output(client, ui, monkeypatch):
    _install_fake_live_graph(ui, monkeypatch)
    response = client.post("/runs", data=_valid_form(), follow_redirects=False)
    run_id = response.headers["location"].rsplit("/", 1)[-1]

    result = client.get(f"/runs/{run_id}")

    assert result.status_code == 200
    assert "Repurposed content package" in result.text
    assert "Source Summary" in result.text or "status-error" in result.text
    assert "LLM drafts used" in result.text
    assert "Fallback happened" in result.text


def test_result_page_presents_needs_human_as_quality_gate_and_cleans_drafts(client, ui):
    run_id = "needs-human-display"
    record = {
        "run_id": run_id,
        "created_at": "2026-06-13T00:00:00+00:00",
        "provider_mode": "gcp",
        "source_type": "raw_article_text",
        "input": {},
        "generation": {"llm_drafts_used": 4, "fell_back": False},
        "package": ui._package_to_dict(_needs_human_display_package(ui)),
    }
    ui._save_run(record)

    result = client.get(f"/runs/{run_id}")

    assert result.status_code == 200
    assert "The agent completed successfully, but human review is required before use." in result.text
    assert "generic_content" in result.text
    assert "platform_mismatch" in result.text
    assert "1/5 1/5" not in result.text
    assert result.text.count("Thread opening about async docs.") == 1
    assert result.text.count("LinkedIn duplicated hook sentence.") == 1
    assert result.text.count("Instagram duplicated hook sentence.") == 1
    assert "#shortvideo" not in result.text


def test_missing_run_id_returns_404(client):
    response = client.get("/runs/not-a-real-run")
    assert response.status_code == 404


def test_ui_import_does_not_require_gcp_credentials(monkeypatch):
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    code = f"""
import importlib.util
import sys

banned = ("google.cloud.storage", "google.cloud.speech", "vertexai", "boto3", "botocore", "azure")
before = set(sys.modules)
spec = importlib.util.spec_from_file_location("agent02_ui_import_probe", r"{APP_PATH}")
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
new_imports = set(sys.modules) - before
imported = sorted(name for name in new_imports if name.startswith(banned))
if imported:
    print(imported)
    raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-W", "error", "-c", code],
        cwd=str(APP_PATH.parents[2]),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_live_mode_works_with_fake_graph(client, ui, monkeypatch):
    _install_fake_live_graph(ui, monkeypatch)
    response = client.post("/runs", data=_valid_form(), follow_redirects=True)

    assert response.status_code == 200
    assert "gcp" in response.text
    assert "mock" not in response.text.lower()


def test_unexpected_error_text_never_leaks_to_record_or_page(client, ui, monkeypatch):
    monkeypatch.setenv("VERTEX_AI_PROJECT", "agents-platform-1212")

    def _boom(*args, **kwargs):
        raise ValueError("RAW_INTERNAL_CANARY: vertex_project secret /etc/path leaked")

    monkeypatch.setattr(ui, "run_agent", _boom)

    response = client.post("/runs", data=_valid_form(), follow_redirects=False)
    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)

    notes = record["package"]["notes"]
    assert record["package"]["status"] == "error"
    assert "RAW_INTERNAL_CANARY" not in notes
    assert "leaked" not in notes
    assert "ValueError" in notes

    page = client.get(f"/runs/{run_id}")
    assert "RAW_INTERNAL_CANARY" not in page.text
    assert "could not start" in page.text
