"""Minimal internal UI for Agent 06.

FastAPI + Jinja2 + local JSON files. This is a thin wrapper around the
Agent 06 graph and provider factory; it does not duplicate agent logic or
import cloud SDKs directly.
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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "agent-06-whitepaper-development"
RUNS_DIR = APP_DIR / "runs"

RUNS_DIR.mkdir(parents=True, exist_ok=True)

for import_path in (REPO_ROOT / "packages", AGENT_DIR):
    import_path_s = str(import_path)
    sys.path = [
        item
        for item in sys.path
        if item and str(Path(item).resolve()) != str(import_path.resolve())
    ]
    sys.path.insert(0, import_path_s)


def _clear_stale_agent_modules() -> None:
    for name in [key for key in sys.modules if key == "agent" or key.startswith("agent.")]:
        sys.modules.pop(name, None)


_clear_stale_agent_modules()

from agent.schemas import CostUsage, WhitepaperDevelopmentPackage  # noqa: E402
from agent.workflow import build_graph  # noqa: E402
from core.config.loader import load_config  # noqa: E402
from core.factory import get_llm_provider, get_telemetry  # noqa: E402


app = FastAPI(title="Agent 06 Whitepaper Development UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


class UserFacingError(ValueError):
    """A safe, UI-authored validation/config message that can be rendered."""


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _selected_provider_mode() -> str:
    selected = (os.environ.get("AGENT06_UI_PROVIDER") or "mock").strip().lower()
    if selected in ("mock", "offline", ""):
        return "mock"
    if selected in ("gcp", "vertex", "live"):
        return "gcp"
    raise ValueError(f"Unsupported AGENT06_UI_PROVIDER={selected!r}; expected mock or gcp")


def load_agent_config(mode: str | None = None) -> dict[str, Any]:
    selected = mode or _selected_provider_mode()
    base = load_config(AGENT_DIR / "config" / "base.yaml")
    if selected == "mock":
        return base
    if selected == "gcp":
        overlay = load_config(AGENT_DIR / "config" / "gcp.yaml")
        return _deep_merge(base, overlay)
    raise ValueError("Agent 06 UI supports provider modes: mock, gcp")


def _run_path(run_id: str) -> Path:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=404, detail="run not found")
    return RUNS_DIR / f"{run_id}.json"


def _empty_cost() -> dict[str, Any]:
    return CostUsage(stage_costs=(), total_inr=0.0).model_dump(mode="json")


def _serializable_error(message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "package_id": "",
        "request_summary": "",
        "title_options": (),
        "recommended_angle": "",
        "executive_summary": "",
        "target_audience_and_pain_points": "",
        "problem_statement": "",
        "industry_context": "",
        "proposed_solution": "",
        "benefits": "",
        "use_cases": "",
        "implementation_approach": "",
        "risks_and_challenges": "",
        "conclusion": "",
        "cta": "",
        "key_claims": (),
        "missing_evidence": (),
        "missing_inputs": (),
        "risk_flags": (),
        "generic_content_flags": (),
        "quality_score": None,
        "pass_status": "fail",
        "improvement_suggestions": (),
        "cost": _empty_cost(),
        "notes": message,
        "generation_used_llm": False,
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


def _package_to_dict(pkg: WhitepaperDevelopmentPackage) -> dict[str, Any]:
    return pkg.model_dump(mode="json")


def _build_graph_from_config(cfg: dict[str, Any]):
    llm = get_llm_provider(cfg)
    telemetry = get_telemetry(cfg)
    return build_graph(cfg, llm, telemetry)


def _missing_gcp_env() -> list[str]:
    return [name for name in ("VERTEX_AI_PROJECT",) if not os.environ.get(name)]


def _require_gcp_live_env() -> None:
    missing = _missing_gcp_env()
    if missing:
        raise UserFacingError(
            "GCP live mode needs VERTEX_AI_PROJECT and Google ADC before developing the package. "
            f"Missing environment variable(s): {', '.join(missing)}. "
            "Set VERTEX_AI_PROJECT to your billing-enabled GCP project and authenticate with "
            "Google Application Default Credentials (run `gcloud auth application-default login`, "
            "or set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON), then retry."
        )


def _validate_required(label: str, value: object) -> str:
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        raise UserFacingError(f"{label} is required")
    return cleaned


def _split_text_items(value: object) -> list[str]:
    raw = str(value or "").replace("\n", ",").replace(";", ",").split(",")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        cleaned = " ".join(item.split())
        key = cleaned.lower()
        if cleaned and key not in seen:
            out.append(cleaned)
            seen.add(key)
    return out


def _build_agent_input(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": _validate_required("Topic", payload.get("topic", "")),
        "company_context": _validate_required("Company/product context", payload.get("company_context", "")),
        "target_audience": _validate_required("Target audience", payload.get("target_audience", "")),
        "industry": _validate_required("Industry", payload.get("industry", "")),
        "problem": _validate_required("Problem", payload.get("problem", "")),
        "solution": _validate_required("Solution", payload.get("solution", "")),
        "tone": _validate_required("Tone", payload.get("tone", "")),
        "target_depth": _validate_required("Target depth", payload.get("target_depth", "")),
        "cta": _validate_required("CTA", payload.get("cta", "")),
        "proof_points": _split_text_items(payload.get("proof_points", "")),
        "source_notes": _split_text_items(payload.get("source_notes", "")),
        "differentiators": _split_text_items(payload.get("differentiators", "")),
        "objections": _split_text_items(payload.get("objections", "")),
        "compliance_constraints": _split_text_items(payload.get("compliance_constraints", "")),
        "excluded_claims": _split_text_items(payload.get("excluded_claims", "")),
    }


def run_agent(raw_input: dict[str, Any], *, provider_mode: str = "mock") -> WhitepaperDevelopmentPackage:
    if provider_mode == "gcp":
        _require_gcp_live_env()
    cfg = load_agent_config(provider_mode)
    graph = _build_graph_from_config(cfg)
    result = graph.invoke({"raw_input": raw_input})
    return result["final_output"]


def _view_model(record: dict[str, Any]) -> dict[str, Any]:
    package = record["package"]
    return {
        "record": record,
        "package": package,
        "score": package.get("quality_score") or {},
        "claims": package.get("key_claims") or [],
        "risks": package.get("risk_flags") or [],
        "generic_flags": package.get("generic_content_flags") or [],
    }


async def _payload_from_request(request: Request) -> tuple[dict[str, Any], bool]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        raw = await request.json()
        if not isinstance(raw, dict):
            raise UserFacingError("JSON request body must be an object")
        return raw, True
    form = await request.form()
    return dict(form), False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    provider_mode = _selected_provider_mode()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "provider_mode": provider_mode,
            "missing_gcp_env": _missing_gcp_env() if provider_mode == "gcp" else [],
        },
    )


@app.post("/develop")
async def develop(request: Request):
    provider_mode = _selected_provider_mode()
    is_json = False
    run_id = uuid.uuid4().hex
    try:
        payload, is_json = await _payload_from_request(request)
        raw_input = payload if is_json else _build_agent_input(payload)
        package = _package_to_dict(run_agent(raw_input, provider_mode=provider_mode))
    except UserFacingError as exc:
        raw_input = {}
        package = _serializable_error(str(exc))
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        raw_input = {}
        package = _serializable_error(
            f"The run could not start ({type(exc).__name__}). Check the terminal running "
            "uvicorn for details, verify the provider configuration, and try again."
        )

    record = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_mode": provider_mode,
        "input": raw_input,
        "package": package,
    }
    _save_run(record)
    if is_json:
        status_code = 200 if package.get("status") != "error" else 400
        return JSONResponse(package, status_code=status_code)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def show_run(request: Request, run_id: str) -> HTMLResponse:
    record = _load_run(run_id)
    return templates.TemplateResponse(request, "result.html", _view_model(record))
