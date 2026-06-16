"""Minimal internal UI for Agent 07.

FastAPI + Jinja2 + local JSON files. This is a thin wrapper around the
Agent 07 graph and provider factory; it does not duplicate agent logic or
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
AGENT_DIR = REPO_ROOT / "agents" / "agent-07-case-study-generation"
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

from agent.schemas import CaseStudyPackage, CostUsage, QualityDimensionScore, QualityReport  # noqa: E402
from agent.workflow import build_graph  # noqa: E402
from core.config.loader import load_config  # noqa: E402
from core.factory import get_llm_provider, get_telemetry  # noqa: E402


app = FastAPI(title="Agent 07 Case Study Generation UI", version="0.1.0")
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
    selected = (os.environ.get("AGENT07_UI_PROVIDER") or "mock").strip().lower()
    if selected in ("mock", "offline", ""):
        return "mock"
    if selected in ("gcp", "vertex", "live"):
        return "gcp"
    raise ValueError(f"Unsupported AGENT07_UI_PROVIDER={selected!r}; expected mock or gcp")


def load_agent_config(mode: str | None = None) -> dict[str, Any]:
    selected = mode or _selected_provider_mode()
    base = load_config(AGENT_DIR / "config" / "base.yaml")
    if selected == "mock":
        return base
    if selected == "gcp":
        overlay = load_config(AGENT_DIR / "config" / "gcp.yaml")
        return _deep_merge(base, overlay)
    raise ValueError("Agent 07 UI supports provider modes: mock, gcp")


def _run_path(run_id: str) -> Path:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=404, detail="run not found")
    return RUNS_DIR / f"{run_id}.json"


def _empty_cost() -> dict[str, Any]:
    return CostUsage(stage_costs=(), total_inr=0.0, cost_ceiling_inr=25.0).model_dump(mode="json")


def _empty_quality(message: str) -> dict[str, Any]:
    dimensions = (
        QualityDimensionScore(name="challenge_clarity", score=0, max_score=15),
        QualityDimensionScore(name="solution_specificity", score=0, max_score=15),
        QualityDimensionScore(name="evidence_backed_results", score=0, max_score=20),
        QualityDimensionScore(name="credibility_claim_safety", score=0, max_score=15),
        QualityDimensionScore(name="structure_completeness", score=0, max_score=10),
        QualityDimensionScore(name="brand_tone_fit", score=0, max_score=10),
        QualityDimensionScore(name="readability", score=0, max_score=10),
        QualityDimensionScore(name="cta_usefulness", score=0, max_score=5),
    )
    return QualityReport(
        overall_score=0,
        dimension_scores=dimensions,
        approval_reason=message,
        revision_notes=(message,),
        passed=False,
    ).model_dump(mode="json")


def _serializable_error(message: str) -> dict[str, Any]:
    return {
        "request_id": "",
        "status": "reject",
        "pass_status": "fail",
        "recommended_title": None,
        "title_options": (),
        "executive_summary": None,
        "customer_background": None,
        "challenge_section": None,
        "solution_section": None,
        "implementation_section": None,
        "results_section": None,
        "metric_highlights": (),
        "pull_quotes": (),
        "customer_quote_placeholders": (),
        "cta_suggestions": (),
        "final_markdown_draft": None,
        "missing_information_warnings": (),
        "risk_flags": (),
        "quality_report": _empty_quality(message),
        "cost_usage": _empty_cost(),
        "notes": message,
        "improvement_suggestions": (),
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


def _package_to_dict(pkg: CaseStudyPackage) -> dict[str, Any]:
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
            "GCP live mode needs VERTEX_AI_PROJECT and Google ADC before generating the package. "
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


def _parse_metrics(value: object) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    for line in str(value or "").splitlines():
        cleaned = " ".join(line.split())
        if not cleaned:
            continue
        if "|" in cleaned:
            parts = [part.strip() for part in cleaned.split("|")]
        elif ":" in cleaned:
            parts = [part.strip() for part in cleaned.split(":", 1)]
        else:
            parts = ["Result metric", cleaned]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        metric = {"label": parts[0], "value": parts[1]}
        if len(parts) >= 3 and parts[2]:
            metric["source"] = parts[2]
        if len(parts) >= 4 and parts[3]:
            metric["baseline"] = parts[3]
        if len(parts) >= 5 and parts[4]:
            metric["after"] = parts[4]
        metrics.append(metric)
    return metrics


def _checkbox(value: object) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _build_agent_input(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "customer_name": " ".join(str(payload.get("customer_name", "")).split()) or None,
        "anonymize_customer": _checkbox(payload.get("anonymize_customer")),
        "industry": _validate_required("Industry", payload.get("industry", "")),
        "target_audience": _validate_required("Target audience", payload.get("target_audience", "")),
        "challenge": _validate_required("Challenge", payload.get("challenge", "")),
        "solution_summary": _validate_required("Solution summary", payload.get("solution_summary", "")),
        "product_or_service": " ".join(str(payload.get("product_or_service", "")).split()) or None,
        "implementation_notes": " ".join(str(payload.get("implementation_notes", "")).split()) or None,
        "results": _validate_required("Results", payload.get("results", "")),
        "metrics": _parse_metrics(payload.get("metrics", "")),
        "customer_quotes": _split_text_items(payload.get("customer_quotes", "")),
        "source_notes": " ".join(str(payload.get("source_notes", "")).split()) or None,
        "brand_voice": " ".join(str(payload.get("brand_voice", "")).split()) or None,
        "tone": str(payload.get("tone", "professional") or "professional"),
        "cta_goal": " ".join(str(payload.get("cta_goal", "")).split()) or None,
        "output_length": str(payload.get("output_length", "standard") or "standard"),
    }


def run_agent(raw_input: dict[str, Any], *, provider_mode: str = "mock") -> CaseStudyPackage:
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
        "metrics": package.get("metric_highlights") or [],
        "warnings": package.get("missing_information_warnings") or [],
        "risks": package.get("risk_flags") or [],
        "placeholders": package.get("customer_quote_placeholders") or [],
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


@app.post("/generate")
async def generate(request: Request):
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
        status_code = 200 if package.get("status") != "reject" or raw_input else 400
        return JSONResponse(package, status_code=status_code)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def show_run(request: Request, run_id: str) -> HTMLResponse:
    record = _load_run(run_id)
    return templates.TemplateResponse(request, "result.html", _view_model(record))
