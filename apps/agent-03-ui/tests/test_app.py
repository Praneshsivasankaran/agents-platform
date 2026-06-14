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
    spec = importlib.util.spec_from_file_location("agent03_ui_app_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT03_UI_PROVIDER", "mock")
    module = _load_app_module()
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    module.RUNS_DIR.mkdir()
    return module


@pytest.fixture()
def client(ui):
    return TestClient(ui.app)


def _valid_form(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "campaign_goal": "Build awareness for an AI-assisted content planning product",
        "product_or_service": "ContentIQ",
        "target_audience": "B2B marketing managers at growing SaaS companies",
        "industry": "B2B SaaS",
        "brand_tone_preset": "clear, practical, confident",
        "brand_tone_custom": "",
        "key_message": "AI agents turn campaign context into structured content ideas faster.",
        "optional_keywords": "content planning, AI agents, campaign strategy",
        "optional_notes": "Use practical angles and proof placeholders.",
        "optional_constraints": "Avoid unsupported percentage claims, avoid heavy jargon",
        "optional_content_type_preference": ["Blog", "LinkedIn post", "Newsletter"],
        "number_of_ideas": "6",
    }
    data.update(overrides)
    return data


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_form_page_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Generate Ideas" in response.text
    assert "offline test mode" in response.text
    assert "Campaign goal" in response.text
    assert "Product/service" in response.text
    assert "Constraints/things to avoid" in response.text
    assert "Generating ideas..." in response.text


def test_post_valid_mock_input_creates_run_json_and_redirects(client, ui):
    response = client.post("/runs", data=_valid_form(), follow_redirects=False)

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["provider_mode"] == "mock"
    assert record["input"]["campaign_goal"].startswith("Build awareness")
    assert record["package"]["status"] == "pass"
    assert record["package"]["content_ideas"]
    assert (ui.RUNS_DIR / f"{run_id}.json").exists()


def test_post_missing_required_input_creates_safe_error_result(client, ui):
    response = client.post(
        "/runs",
        data=_valid_form(campaign_goal="  "),
        follow_redirects=False,
    )

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "Campaign goal is required" in record["package"]["notes"]


def test_gcp_start_page_warns_when_env_missing(client, monkeypatch):
    monkeypatch.setenv("AGENT03_UI_PROVIDER", "gcp")
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)

    response = client.get("/")

    assert response.status_code == 200
    assert "GCP live" in response.text
    assert "GCP live mode is missing" in response.text
    assert "VERTEX_AI_PROJECT" in response.text


def test_gcp_mode_without_env_renders_actionable_error(client, ui, monkeypatch):
    monkeypatch.setenv("AGENT03_UI_PROVIDER", "gcp")
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)

    response = client.post("/runs", data=_valid_form(), follow_redirects=False)

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "GCP live mode needs VERTEX_AI_PROJECT" in record["package"]["notes"]
    assert "SecretStore returned None" not in record["package"]["notes"]


def test_result_page_renders_content_ideation_sections(client):
    response = client.post("/runs", data=_valid_form(), follow_redirects=False)
    run_id = response.headers["location"].rsplit("/", 1)[-1]

    result = client.get(f"/runs/{run_id}")

    assert result.status_code == 200
    assert "Content ideation package" in result.text
    assert "Campaign Summary" in result.text
    assert "Audience Insights" in result.text
    assert "Content Ideas" in result.text
    assert "Blog Brief For Agent 01" in result.text
    assert "Repurposing Brief For Agent 02" in result.text
    assert "Quality Report" in result.text


def test_result_page_handles_error_record(client, ui):
    response = client.post(
        "/runs",
        data=_valid_form(product_or_service=""),
        follow_redirects=False,
    )
    run_id = response.headers["location"].rsplit("/", 1)[-1]

    result = client.get(f"/runs/{run_id}")

    assert result.status_code == 200
    assert "Product or service is required" in result.text
    assert "status-error" in result.text


def test_missing_run_id_returns_404(client):
    response = client.get("/runs/not-a-real-run")
    assert response.status_code == 404


def test_unexpected_error_text_never_leaks_into_notes(client, ui, monkeypatch):
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


def test_ui_import_does_not_import_cloud_sdks(monkeypatch):
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    code = f"""
import importlib.util
import sys

banned = ("google.cloud.storage", "google.cloud.speech", "vertexai", "boto3", "botocore", "azure")
before = set(sys.modules)
spec = importlib.util.spec_from_file_location("agent03_ui_import_probe", r"{APP_PATH}")
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

