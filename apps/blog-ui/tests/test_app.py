from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _load_app_module():
    spec = importlib.util.spec_from_file_location("blog_ui_app_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOG_UI_PROVIDER", "mock")
    module = _load_app_module()
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(module, "UPLOADS_DIR", tmp_path / "uploads")
    module.RUNS_DIR.mkdir()
    module.UPLOADS_DIR.mkdir()
    return module


@pytest.fixture()
def client(ui):
    return TestClient(ui.app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_form_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Generate Blog" in response.text
    assert "offline test mode" in response.text
    assert "Provider mode" not in response.text
    assert "GCP live" not in response.text


def test_gcp_start_page_warns_when_env_missing(client, monkeypatch):
    monkeypatch.setenv("BLOG_UI_PROVIDER", "gcp")
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    monkeypatch.delenv("GCS_BLOG_BUCKET", raising=False)
    response = client.get("/")

    assert response.status_code == 200
    assert "Current provider" in response.text
    assert "GCP live" in response.text
    assert "GCP live mode is missing" in response.text
    assert "VERTEX_AI_PROJECT" in response.text
    assert "GCS_BLOG_BUCKET" in response.text


def test_text_run_succeeds_on_mock_provider(client, ui):
    response = client.post(
        "/runs",
        data={
            "input_type": "text",
            "raw_text": "Machine learning is changing healthcare workflows.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["input_type"] == "text"
    assert record["provider_mode"] == "mock"
    assert record["package"]["status"] in {"pass", "needs_human", "stopped_cost_ceiling", "error"}


def test_empty_text_input_renders_error_result(client, ui):
    response = client.post(
        "/runs",
        data={"input_type": "text", "raw_text": "   "},
        follow_redirects=False,
    )
    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "Text input is required" in record["package"]["notes"]


def test_gcp_mode_without_env_renders_actionable_error(client, ui, monkeypatch):
    monkeypatch.setenv("BLOG_UI_PROVIDER", "gcp")
    monkeypatch.delenv("VERTEX_AI_PROJECT", raising=False)
    monkeypatch.delenv("GCS_BLOG_BUCKET", raising=False)
    response = client.post(
        "/runs",
        data={
            "input_type": "text",
            "raw_text": "AI agents can help teams write better drafts.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    assert "GCP live mode needs these environment variables" in record["package"]["notes"]
    assert "VERTEX_AI_PROJECT" in record["package"]["notes"]
    assert "GCS_BLOG_BUCKET" in record["package"]["notes"]
    assert "SecretStore returned None" not in record["package"]["notes"]


def test_unexpected_error_text_never_leaks_into_notes(client, ui, monkeypatch):
    """A pre-graph failure (e.g. provider construction) must surface as a friendly
    type-name-only message — raw exception text can carry config internals."""
    def _boom(*args, **kwargs):
        raise ValueError("RAW_INTERNAL_CANARY: vertex_project secret /etc/path leaked")

    monkeypatch.setattr(ui, "run_agent", _boom)
    response = client.post(
        "/runs",
        data={"input_type": "text", "raw_text": "AI in healthcare."},
        follow_redirects=False,
    )
    assert response.status_code == 303
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    record = ui._load_run(run_id)
    assert record["package"]["status"] == "error"
    notes = record["package"]["notes"]
    assert "RAW_INTERNAL_CANARY" not in notes
    assert "leaked" not in notes
    assert "ValueError" in notes  # type name only
    assert "could not start" in notes  # friendly, actionable phrasing
    # And the rendered page must not leak it either.
    page = client.get(f"/runs/{run_id}")
    assert "RAW_INTERNAL_CANARY" not in page.text


def test_result_page_renders_stored_output(client):
    response = client.post(
        "/runs",
        data={
            "input_type": "text",
            "raw_text": "AI agents can be cloud agnostic with provider interfaces.",
        },
        follow_redirects=False,
    )
    run_id = response.headers["location"].rsplit("/", 1)[-1]
    result = client.get(f"/runs/{run_id}")
    assert result.status_code == 200
    assert "Run " in result.text
    assert "Stage costs" in result.text
    assert 'class="summary"' in result.text


def test_voice_upload_file_is_cleaned_after_run(client, ui):
    response = client.post(
        "/runs",
        data={"input_type": "voice"},
        files={"upload": ("voice.wav", b"not a real wav but mock does not inspect it", "audio/wav")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert [p.name for p in ui.UPLOADS_DIR.iterdir()] == []


def test_oversized_upload_returns_413_and_leaves_no_file(client, ui, monkeypatch):
    monkeypatch.setenv("BLOG_UI_MAX_UPLOAD_BYTES", "8")
    response = client.post(
        "/runs",
        data={"input_type": "voice"},
        files={"upload": ("voice.wav", b"this is larger than eight bytes", "audio/wav")},
        follow_redirects=False,
    )

    assert response.status_code == 413
    assert "too large" in response.text
    assert "8 bytes" in response.text
    assert [p.name for p in ui.UPLOADS_DIR.iterdir()] == []


def test_cloud_sdk_not_imported_by_ui_import():
    code = f"""
import importlib.util
import sys

banned = ("google.cloud.storage", "google.cloud.speech", "vertexai", "boto3", "botocore", "azure")
before = set(sys.modules)
spec = importlib.util.spec_from_file_location("blog_ui_import_probe", r"{APP_PATH}")
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
