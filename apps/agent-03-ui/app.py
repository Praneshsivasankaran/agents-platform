"""Minimal internal UI for Agent 03.

FastAPI + Jinja2 + local JSON files. This is a thin wrapper around the
existing Agent 03 graph and provider factory; it does not duplicate agent logic
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

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "agent-03-content-ideation"
RUNS_DIR = APP_DIR / "runs"

RUNS_DIR.mkdir(parents=True, exist_ok=True)

for import_path in (REPO_ROOT / "packages", AGENT_DIR):
    import_path_s = str(import_path)
    if import_path_s not in sys.path:
        sys.path.insert(0, import_path_s)

from agent.contracts import ContentIdeationPackage, CostUsage  # noqa: E402
from agent.graph import build_graph  # noqa: E402
from core.config.loader import load_config  # noqa: E402
from core.factory import get_llm_provider, get_telemetry  # noqa: E402


app = FastAPI(title="Agent 03 Content Ideation UI", version="0.1.0")
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
    selected = (os.environ.get("AGENT03_UI_PROVIDER") or "mock").strip().lower()
    if selected in ("mock", "offline", ""):
        return "mock"
    if selected in ("gcp", "vertex", "live"):
        return "gcp"
    raise ValueError(f"Unsupported AGENT03_UI_PROVIDER={selected!r}; expected mock or gcp")


def load_agent_config(mode: str | None = None) -> dict[str, Any]:
    selected = mode or _selected_provider_mode()
    base = load_config(AGENT_DIR / "config" / "base.yaml")
    if selected == "mock":
        return base
    if selected == "gcp":
        overlay = load_config(AGENT_DIR / "config" / "gcp.yaml")
        return _deep_merge(base, overlay)
    raise ValueError("Agent 03 UI supports provider modes: mock, gcp")


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
        "campaign_summary": None,
        "audience_insights": None,
        "content_themes": (),
        "content_ideas": (),
        "hooks": (),
        "cta_suggestions": (),
        "recommended_formats": (),
        "quality_score": 0,
        "quality_notes": (),
        "risk_flags": (),
        "blog_brief_for_agent_01": None,
        "repurposing_brief_for_agent_02": None,
        "recommended_next_agent": "Human Review",
        "quality_report": None,
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


def _package_to_dict(pkg: ContentIdeationPackage) -> dict[str, Any]:
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
            "GCP live mode needs VERTEX_AI_PROJECT and Google ADC before generating."
        )


def _validate_required(label: str, value: str) -> str:
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        raise UserFacingError(f"{label} is required")
    return cleaned


def _split_text_items(value: str) -> list[str]:
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


def _brand_tone(preset: str, custom: str) -> str:
    return _validate_required("Brand tone", custom or preset)


def _build_agent_input(
    *,
    campaign_goal: str,
    product_or_service: str,
    target_audience: str,
    industry: str,
    brand_tone_preset: str,
    brand_tone_custom: str,
    key_message: str,
    optional_keywords: str,
    optional_notes: str,
    optional_constraints: str,
    optional_content_type_preference: list[str] | None,
    number_of_ideas: int,
) -> dict[str, Any]:
    if number_of_ideas < 1 or number_of_ideas > 20:
        raise UserFacingError("Number of ideas must be between 1 and 20")
    return {
        "campaign_goal": _validate_required("Campaign goal", campaign_goal),
        "product_or_service": _validate_required("Product or service", product_or_service),
        "target_audience": _validate_required("Target audience", target_audience),
        "industry": _validate_required("Industry", industry),
        "brand_tone": _brand_tone(brand_tone_preset, brand_tone_custom),
        "key_message": _validate_required("Key message", key_message),
        "optional_keywords": _split_text_items(optional_keywords),
        "optional_notes": " ".join(str(optional_notes or "").split()) or None,
        "optional_constraints": _split_text_items(optional_constraints),
        "optional_content_type_preference": list(optional_content_type_preference or []),
        "number_of_ideas": number_of_ideas,
    }


def run_agent(raw_input: dict[str, Any], *, provider_mode: str = "mock") -> ContentIdeationPackage:
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
        "quality": package.get("quality_report") or {},
        "blog_brief": package.get("blog_brief_for_agent_01"),
        "repurposing_brief": package.get("repurposing_brief_for_agent_02"),
    }


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


@app.post("/runs")
async def create_run(
    campaign_goal: str = Form(""),
    product_or_service: str = Form(""),
    target_audience: str = Form(""),
    industry: str = Form(""),
    brand_tone_preset: str = Form("clear, practical, confident"),
    brand_tone_custom: str = Form(""),
    key_message: str = Form(""),
    optional_keywords: str = Form(""),
    optional_notes: str = Form(""),
    optional_constraints: str = Form(""),
    optional_content_type_preference: list[str] | None = Form(default=None),
    number_of_ideas: int = Form(8),
) -> RedirectResponse:
    provider_mode = _selected_provider_mode()
    run_id = uuid.uuid4().hex
    try:
        raw_input = _build_agent_input(
            campaign_goal=campaign_goal,
            product_or_service=product_or_service,
            target_audience=target_audience,
            industry=industry,
            brand_tone_preset=brand_tone_preset,
            brand_tone_custom=brand_tone_custom,
            key_message=key_message,
            optional_keywords=optional_keywords,
            optional_notes=optional_notes,
            optional_constraints=optional_constraints,
            optional_content_type_preference=optional_content_type_preference,
            number_of_ideas=number_of_ideas,
        )
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
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def show_run(request: Request, run_id: str) -> HTMLResponse:
    record = _load_run(run_id)
    return templates.TemplateResponse(request, "result.html", _view_model(record))
