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
    spec = importlib.util.spec_from_file_location("agent04_ui_app_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT04_UI_PROVIDER", "mock")
    module = _load_app_module()
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    module.RUNS_DIR.mkdir()
    return module


@pytest.fixture()
def client(ui):
    return TestClient(ui.app)


def _valid_form(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "draft_content": (
            "AI content agents help marketing teams turn scattered campaign notes into "
            "clear drafts, review packages, and repeatable workflows. A strong workflow "
            "keeps human editors in control while reducing repetitive checks. Teams can "
            "use AI content agents to structure ideas, improve drafts, and prepare content "
            "for search review without inventing claims or removing editorial judgment."
        ),
        "topic": "AI agents for content teams",
        "primary_keyword": "AI content agents",
        "secondary_keywords": "content automation, SEO workflow",
        "target_audience": "marketing managers",
        "content_goal": "educate and generate demo interest",
        "brand_tone": "professional and clear",
        "constraints": "Do not mention pricing",
        "cta_direction": "Book a demo",
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
    assert "Optimize SEO" in response.text
    assert "offline test mode" in response.text
    assert "Draft content" in response.text
    assert "Primary keyword" in response.text


def test_post_valid_mock_input_creates_run_json_and_redirects(client, ui):
    response = client.post("/optimize", data=_valid_form(), follow_redirects=False)

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["provider_mode"] == "mock"
    assert record["input"]["primary_keyword"] == "AI content agents"
    assert record["package"]["status"] == "pass"
    assert record["package"]["optimized_draft"]
    assert (ui.RUNS_DIR / f"{run_id}.json").exists()


def test_json_optimize_returns_package(client):
    response = client.post("/optimize", json=_valid_form())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["url_slug"]


def test_post_missing_required_input_creates_safe_error_result(client, ui):
    response = client.post(
        "/optimize",
        data=_valid_form(primary_keyword="  "),
        follow_redirects=False,
    )

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "Primary keyword is required" in record["package"]["notes"]


def test_gcp_start_page_warns_when_env_missing(client, monkeypatch):
    monkeypatch.setenv("AGENT04_UI_PROVIDER", "gcp")
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)

    response = client.get("/")

    assert response.status_code == 200
    assert "GCP live" in response.text
    assert "VERTEX_AI_PROJECT" in response.text


def test_gcp_mode_without_env_renders_actionable_error(client, ui, monkeypatch):
    monkeypatch.setenv("AGENT04_UI_PROVIDER", "gcp")
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)

    response = client.post("/optimize", data=_valid_form(), follow_redirects=False)

    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "GCP live mode needs VERTEX_AI_PROJECT" in record["package"]["notes"]
    assert "SecretStore returned None" not in record["package"]["notes"]


def test_result_page_renders_sections(client):
    response = client.post("/optimize", data=_valid_form(), follow_redirects=False)
    run_id = response.headers["location"].rsplit("/", 1)[-1]

    result = client.get(f"/runs/{run_id}")

    assert result.status_code == 200
    assert "SEO optimization package" in result.text
    assert "Title Options" in result.text
    assert "Meta Description" in result.text
    assert "Keyword Placement" in result.text
    assert "Optimized Draft" in result.text


def test_unexpected_error_text_never_leaks_into_notes(client, ui, monkeypatch):
    def _boom(*args, **kwargs):
        raise ValueError("RAW_INTERNAL_CANARY: vertex_project secret /etc/path leaked")

    monkeypatch.setattr(ui, "run_agent", _boom)
    response = client.post("/optimize", data=_valid_form(), follow_redirects=False)
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


def test_ui_import_does_not_import_cloud_or_model_sdks(monkeypatch):
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    code = f"""
import importlib.util
import sys

banned = ("google.cloud.storage", "google.cloud.speech", "vertexai", "boto3", "botocore", "azure", "litellm")
before = set(sys.modules)
spec = importlib.util.spec_from_file_location("agent04_ui_import_probe", r"{APP_PATH}")
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
