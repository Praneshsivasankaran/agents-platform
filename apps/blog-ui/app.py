"""Minimal internal UI for Agent 01.

FastAPI + Jinja2 + local JSON files. This is a thin wrapper around the
existing Agent 01 graph and provider factory; it does not duplicate agent logic
or import cloud SDKs directly.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "agent-01-blog-writer"
RUNS_DIR = APP_DIR / "runs"
UPLOADS_DIR = APP_DIR / "uploads"
DEFAULT_MAX_UPLOAD_BYTES = 500 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024

for path in (RUNS_DIR, UPLOADS_DIR):
    path.mkdir(parents=True, exist_ok=True)

for import_path in (REPO_ROOT / "packages", AGENT_DIR):
    import_path_s = str(import_path)
    if import_path_s not in sys.path:
        sys.path.insert(0, import_path_s)

from agent.graph import build_graph  # noqa: E402
from agent.schemas import BlogPackage  # noqa: E402
from core.config.loader import load_config  # noqa: E402
from core.factory import get_llm_provider, get_telemetry, get_transcription_provider  # noqa: E402


app = FastAPI(title="Agent 01 Blog UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


class UserFacingError(ValueError):
    """An error whose message was authored HERE for the user and is safe to render.

    Anything else that escapes a run is collapsed to its exception type name only —
    provider/config exception text can carry secrets references, paths, or internals
    and must never reach the saved run record or the page.
    """


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _selected_provider_mode() -> str:
    selected = (os.environ.get("BLOG_UI_PROVIDER") or "gcp").strip().lower()
    if selected in ("gcp", "vertex", "live"):
        return "gcp"
    if selected in ("mock", "offline"):
        return "mock"
    raise ValueError(f"Unsupported BLOG_UI_PROVIDER={selected!r}; expected gcp or mock")


def load_agent_config(mode: str | None = None) -> dict[str, Any]:
    """Load Agent 01 config. Default mode is live GCP for the UI."""
    selected = mode or _selected_provider_mode()
    base = load_config(AGENT_DIR / "config" / "base.yaml")
    if selected in ("mock", "offline", ""):
        return base
    if selected in ("gcp", "vertex", "live"):
        overlay = load_config(AGENT_DIR / "config" / "gcp.yaml")
        return _deep_merge(base, overlay)
    raise ValueError(f"Unsupported BLOG_UI_PROVIDER={selected!r}; expected mock or gcp")


def _run_path(run_id: str) -> Path:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=404, detail="run not found")
    return RUNS_DIR / f"{run_id}.json"


def _serializable_error(message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "title": None,
        "full_draft": None,
        "source_notes": (),
        "quality": None,
        "hard_fail_flags": (),
        "improvement_suggestions": (),
        "cost": {"total_inr": 0.0, "stage_costs": ()},
        "notes": message,
        "revision_count": 0,
        "alternative_titles": (),
        "short_summary": None,
        "seo_keywords": (),
        "suggested_tags": (),
        "meta_description": None,
    }


def _save_run(record: dict[str, Any]) -> None:
    _run_path(record["run_id"]).write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _load_run(run_id: str) -> dict[str, Any]:
    path = _run_path(run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="run not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _package_to_dict(pkg: BlogPackage) -> dict[str, Any]:
    return pkg.model_dump(mode="json")


def _build_graph_from_config(cfg: dict[str, Any]):
    llm = get_llm_provider(cfg)
    telemetry = get_telemetry(cfg)
    transcription = get_transcription_provider(cfg)
    return build_graph(cfg, llm, telemetry, transcription)


def _missing_gcp_env() -> list[str]:
    return [name for name in ("VERTEX_AI_PROJECT", "GCS_BLOG_BUCKET") if not os.environ.get(name)]


def _require_gcp_live_env() -> None:
    missing = _missing_gcp_env()
    if missing:
        joined = ", ".join(missing)
        raise UserFacingError(
            "GCP live mode needs these environment variables in the same PowerShell "
            f"window that starts the UI: {joined}. Stop uvicorn, set them, then restart."
        )


def run_agent(input_type: str, raw_input: str, *, provider_mode: str = "mock") -> BlogPackage:
    if provider_mode == "gcp":
        _require_gcp_live_env()
    cfg = load_agent_config(provider_mode)
    graph = _build_graph_from_config(cfg)
    result = graph.invoke({"raw_input": raw_input, "input_type": input_type})
    return result["final_output"]


def _safe_suffix(filename: str, input_type: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix:
        return suffix
    return ".mp4" if input_type == "video" else ".wav"


def _max_upload_bytes() -> int:
    raw = os.environ.get("BLOG_UI_MAX_UPLOAD_BYTES")
    if raw is None or not raw.strip():
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        value = int(raw)
    except ValueError:
        raise ValueError("BLOG_UI_MAX_UPLOAD_BYTES must be a positive integer") from None
    if value <= 0:
        raise ValueError("BLOG_UI_MAX_UPLOAD_BYTES must be a positive integer")
    return value


def _format_bytes(size: int) -> str:
    if size >= 1024 * 1024 and size % (1024 * 1024) == 0:
        return f"{size // (1024 * 1024)} MB"
    if size >= 1024 and size % 1024 == 0:
        return f"{size // 1024} KB"
    return f"{size} bytes"


async def _store_upload(upload: UploadFile, input_type: str, run_id: str) -> Path:
    destination = UPLOADS_DIR / f"{run_id}{_safe_suffix(upload.filename or '', input_type)}"
    max_bytes = _max_upload_bytes()
    total = 0
    try:
        with destination.open("wb") as out:
            while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Upload is too large. Maximum allowed size is "
                            f"{_format_bytes(max_bytes)}."
                        ),
                    )
                out.write(chunk)
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise




@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    provider_mode = _selected_provider_mode()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"provider_mode": provider_mode, "missing_gcp_env": _missing_gcp_env() if provider_mode == "gcp" else []},
    )


@app.post("/runs")
async def create_run(
    input_type: str = Form("text"),
    raw_text: str = Form(""),
    upload: UploadFile | None = File(default=None),
) -> RedirectResponse:
    normalized_type = (input_type or "text").strip().lower()
    if normalized_type not in {"text", "voice", "video"}:
        raise HTTPException(status_code=400, detail="input_type must be text, voice, or video")
    provider_mode = _selected_provider_mode()

    run_id = uuid.uuid4().hex
    upload_path: Path | None = None
    try:
        if normalized_type == "text":
            raw_input = (raw_text or "").strip()
            if not raw_input:
                raise UserFacingError("Text input is required")
        else:
            if upload is None or not upload.filename:
                raise UserFacingError(f"A {normalized_type} upload is required")
            upload_path = await _store_upload(upload, normalized_type, run_id)
            raw_input = str(upload_path)

        package = _package_to_dict(run_agent(normalized_type, raw_input, provider_mode=provider_mode))
    except HTTPException:
        raise
    except UserFacingError as exc:
        package = _serializable_error(str(exc))
    except Exception as exc:
        # Fail closed: never render str(exc) — provider/config exception text can carry
        # internals (paths, secret key names, response fragments). Type name only in the
        # record/page; the full traceback goes to the server terminal for the operator.
        traceback.print_exc(file=sys.stderr)
        package = _serializable_error(
            f"The run could not start ({type(exc).__name__}). Check the terminal running "
            "uvicorn for details, verify the GCP configuration, and try again."
        )
    finally:
        if upload_path is not None:
            upload_path.unlink(missing_ok=True)
        if upload is not None:
            await upload.close()

    record = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_type": normalized_type,
        "provider_mode": provider_mode,
        "package": package,
    }
    _save_run(record)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def show_run(request: Request, run_id: str) -> HTMLResponse:
    record = _load_run(run_id)
    return templates.TemplateResponse(
        request,
        "result.html",
        {"record": record, "package": record["package"]},
    )
