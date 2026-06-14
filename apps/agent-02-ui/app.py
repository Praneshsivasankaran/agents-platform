"""Minimal internal UI for Agent 02.

FastAPI + Jinja2 + local JSON files. This is a thin wrapper around the
existing Agent 02 graph and provider factory; it does not duplicate agent logic
or import cloud SDKs directly.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
import uuid
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Form, HTTPException, Request
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "agent-02-content-repurposer"
RUNS_DIR = APP_DIR / "runs"

RUNS_DIR.mkdir(parents=True, exist_ok=True)

for import_path in (REPO_ROOT / "packages", AGENT_DIR):
    import_path_s = str(import_path)
    while import_path_s in sys.path:
        sys.path.remove(import_path_s)
    sys.path.insert(0, import_path_s)

# Test runs may already have another top-level `agent` package loaded.
# This UI is specifically bound to Agent 02, so clear stale Agent 01 modules first.
for module_name in [name for name in sys.modules if name == "agent" or name.startswith("agent.")]:
    module = sys.modules.get(module_name)
    module_file = str(getattr(module, "__file__", ""))
    if "agent-02-content-repurposer" not in module_file:
        sys.modules.pop(module_name, None)

from agent.graph import build_graph  # noqa: E402
from agent.schemas import CostUsage, RepurposedContentPackage  # noqa: E402
from core.config.loader import load_config  # noqa: E402
from core.factory import get_llm_provider, get_object_storage, get_telemetry  # noqa: E402
from core.interfaces import Telemetry, Usage  # noqa: E402


app = FastAPI(title="Agent 02 Content Repurposer UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

_THREAD_PREFIX_RE = re.compile(r"^\s*(?:\d+\s*/\s*\d+|\d+[.)])\s*")
_WHITESPACE_RE = re.compile(r"\s+")


class UserFacingError(ValueError):
    """A safe, UI-authored validation/config message that can be rendered."""


class CapturingTelemetry(Telemetry):
    """Delegate telemetry while keeping trusted event fields for the local result page."""

    def __init__(self, inner: Telemetry) -> None:
        self.inner = inner
        self.events: list[tuple[str, dict[str, Any]]] = []

    def log(self, msg: str, **fields: Any) -> None:
        self.events.append((msg, dict(fields)))
        self.inner.log(msg, **fields)

    def metric(self, name: str, value: float, **tags: Any) -> None:
        self.inner.metric(name, value, **tags)

    def record_usage(self, usage: Usage, **tags: Any) -> None:
        self.inner.record_usage(usage, **tags)

    def span(self, name: str, **attrs: Any) -> AbstractContextManager[str]:
        return self.inner.span(name, **attrs)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _selected_provider_mode() -> str:
    """Manual UI runs are always live GCP/Vertex/LiteLLM."""
    return "gcp"


def load_agent_config(mode: str | None = None) -> dict[str, Any]:
    """Load Agent 02 live config for the local UI."""
    selected = mode or _selected_provider_mode()
    base = load_config(AGENT_DIR / "config" / "base.yaml")
    if selected == "gcp":
        overlay = load_config(AGENT_DIR / "config" / "gcp.yaml")
        return _deep_merge(base, overlay)
    raise ValueError("Agent 02 UI only supports live GCP/Vertex mode")


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
        "source_summary": "",
        "content_brief": "",
        "platform_outputs": (),
        "markdown_review_package": "",
        "output_package_uri": None,
        "validation_report": (),
        "factual_consistency_report": None,
        "usefulness_report": None,
        "quality_report": None,
        "cta_options": (),
        "hashtag_sets": (),
        "cost": _empty_cost(),
        "hard_fails": (),
        "improvement_suggestions": (),
        "notes": message,
        "revision_count": 0,
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


def _package_to_dict(pkg: RepurposedContentPackage) -> dict[str, Any]:
    return pkg.model_dump(mode="json")


def _generation_summary(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    for msg, fields in events:
        if msg == "generate_platform_drafts.complete" and "llm_drafts_used" in fields:
            return {
                "llm_drafts_used": int(fields.get("llm_drafts_used") or 0),
                "fell_back": bool(fields.get("fell_back", False)),
            }
    return {"llm_drafts_used": None, "fell_back": None}


def _normalized_display_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip()).lower()


def _clean_thread_post(value: Any) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    while cleaned:
        next_value = _THREAD_PREFIX_RE.sub("", cleaned).strip()
        if next_value == cleaned:
            break
        cleaned = next_value
    return cleaned


def _dedupe_texts(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _normalized_display_text(value)
        if value and key not in seen:
            out.append(value)
            seen.add(key)
    return out


def _thread_posts_from_body(body: str) -> list[str]:
    candidates = [part.strip() for part in re.split(r"\n+", body) if part.strip()]
    cleaned = [_clean_thread_post(part) for part in candidates]
    if len(cleaned) < 2:
        return []
    return _dedupe_texts(cleaned)


def _body_repeats_hook(body: Any, hook: Any) -> bool:
    normalized_body = _normalized_display_text(body)
    normalized_hook = _normalized_display_text(hook)
    return bool(normalized_body and normalized_hook and normalized_body.startswith(normalized_hook))


def _clean_draft_for_display(raw_draft: dict[str, Any]) -> dict[str, Any]:
    draft = dict(raw_draft)
    platform = draft.get("platform")
    body = str(draft.get("body") or "")
    hook = str(draft.get("hook") or "")

    if platform == "x_twitter":
        raw_posts = draft.get("thread_posts") or []
        thread_posts = _dedupe_texts([_clean_thread_post(post) for post in raw_posts])
        if not thread_posts:
            thread_posts = _thread_posts_from_body(body)
        if thread_posts:
            draft["thread_posts"] = thread_posts
            draft["hook"] = ""
            draft["body"] = ""
    elif platform in {"linkedin", "instagram"} and _body_repeats_hook(body, hook):
        draft["hook"] = ""
    elif platform == "short_video":
        draft["hashtags"] = []

    return draft


def _display_hashtag_sets(package: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in package.get("hashtag_sets") or []:
        platform = item.get("platform")
        hashtags = item.get("hashtags") or []
        if platform == "short_video" or not hashtags:
            continue
        rows.append(item)
    return rows


def _hard_fail_codes(package: dict[str, Any]) -> list[str]:
    hard_fails = list(package.get("hard_fails") or [])
    quality = package.get("quality_report") or {}
    hard_fails.extend(quality.get("hard_fails") or [])

    codes: list[str] = []
    seen: set[str] = set()
    for fail in hard_fails:
        code = str(fail.get("code") or "").strip()
        if code and code not in seen:
            codes.append(code)
            seen.add(code)
    return codes


def _maybe_object_storage(cfg: dict[str, Any], provider_mode: str):
    """Construct ObjectStorage by factory when local config can support it.

    GCP output storage is optional for this local UI. If a bucket env var is not
    present, the graph still returns the package inline and the UI saves it under
    ``runs/``.
    """
    if provider_mode == "gcp" and not os.environ.get("GCS_BUCKET"):
        return None
    try:
        return get_object_storage(cfg)
    except Exception:  # noqa: BLE001
        return None


def _build_graph_from_config(cfg: dict[str, Any], provider_mode: str):
    llm = get_llm_provider(cfg)
    telemetry = CapturingTelemetry(get_telemetry(cfg))
    object_storage = _maybe_object_storage(cfg, provider_mode)
    graph = build_graph(cfg, llm, telemetry, object_storage)
    return graph, telemetry


def _missing_gcp_env() -> list[str]:
    return [name for name in ("VERTEX_AI_PROJECT",) if not os.environ.get(name)]


def _require_gcp_live_env() -> None:
    missing = _missing_gcp_env()
    if missing:
        raise UserFacingError(
            "Live GCP/Vertex configuration is missing. Please set VERTEX_AI_PROJECT "
            "and authenticate with Google ADC."
        )


def _validate_required(label: str, value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise UserFacingError(f"{label} is required")
    return cleaned


def _optional_json_object(label: str, value: str) -> dict[str, Any] | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        raise UserFacingError(f"{label} must be valid JSON")
    if not isinstance(parsed, dict):
        raise UserFacingError(f"{label} must be a JSON object")
    return parsed


def _normalize_platforms(target_platforms: list[str] | None, include_newsletter: str | None) -> list[str]:
    selected = list(dict.fromkeys(target_platforms or []))
    if include_newsletter and "newsletter" not in selected:
        selected.append("newsletter")
    if not selected:
        raise UserFacingError("Select at least one target platform")
    return selected


def _build_agent_input(
    *,
    source_type: str,
    title: str,
    summary: str,
    full_text: str,
    audience: str,
    brand_tone: str,
    campaign_goal: str,
    cta: str,
    target_platforms: list[str],
    include_newsletter: bool,
    repurposing_brief_from_agent_03: str = "",
) -> dict[str, Any]:
    normalized_source_type = (source_type or "").strip()
    if normalized_source_type not in {"raw_article_text", "agent01_blog_package"}:
        raise UserFacingError("source type must be raw_article_text or agent01_blog_package")

    body_field = "blog_body" if normalized_source_type == "agent01_blog_package" else "full_text"
    source_status = "pass" if normalized_source_type == "agent01_blog_package" else None
    payload: dict[str, Any] = {
        "source_type": normalized_source_type,
        "title": _validate_required("Title", title),
        "summary": _validate_required("Summary", summary),
        body_field: _validate_required("Full blog/article text", full_text),
        "source_status": source_status,
        "target_platforms": tuple(target_platforms),
        "include_newsletter": include_newsletter,
        "audience": _validate_required("Audience", audience),
        "brand_tone": _validate_required("Brand tone", brand_tone),
        "campaign_goal": _validate_required("Campaign goal", campaign_goal),
        "cta": _validate_required("CTA", cta),
    }
    if source_status is None:
        payload.pop("source_status")
    brief = _optional_json_object("Agent 03 repurposing brief", repurposing_brief_from_agent_03)
    if brief is not None:
        payload["repurposing_brief_from_agent_03"] = brief
    return payload


def run_agent(raw_input: dict[str, Any], *, provider_mode: str = "gcp") -> tuple[RepurposedContentPackage, dict[str, Any]]:
    _require_gcp_live_env()
    cfg = load_agent_config(provider_mode)
    graph, telemetry = _build_graph_from_config(cfg, provider_mode)
    result = graph.invoke({"raw_input": raw_input})
    return result["final_output"], _generation_summary(telemetry.events)


def _platform_outputs(package: dict[str, Any]) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for draft in package.get("platform_outputs") or []:
        platform = draft.get("platform")
        if platform:
            outputs[platform] = _clean_draft_for_display(draft)
    return outputs


def _view_model(record: dict[str, Any]) -> dict[str, Any]:
    package = record["package"]
    return {
        "record": record,
        "package": package,
        "outputs": _platform_outputs(package),
        "quality": package.get("quality_report") or {},
        "factual": package.get("factual_consistency_report"),
        "usefulness": package.get("usefulness_report"),
        "generation": record.get("generation", {}),
        "hard_fail_codes": _hard_fail_codes(package),
        "hashtag_sets": _display_hashtag_sets(package),
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
    source_type: str = Form("raw_article_text"),
    title: str = Form(""),
    summary: str = Form(""),
    full_text: str = Form(""),
    audience: str = Form(""),
    brand_tone: str = Form(""),
    campaign_goal: str = Form(""),
    cta: str = Form(""),
    target_platforms: list[str] | None = Form(default=None),
    include_newsletter: str | None = Form(default=None),
    repurposing_brief_from_agent_03: str = Form(""),
) -> RedirectResponse:
    provider_mode = _selected_provider_mode()
    run_id = uuid.uuid4().hex
    generation = {"llm_drafts_used": None, "fell_back": None}
    try:
        platforms = _normalize_platforms(target_platforms, include_newsletter)
        raw_input = _build_agent_input(
            source_type=source_type,
            title=title,
            summary=summary,
            full_text=full_text,
            audience=audience,
            brand_tone=brand_tone,
            campaign_goal=campaign_goal,
            cta=cta,
            target_platforms=platforms,
            include_newsletter=bool(include_newsletter),
            repurposing_brief_from_agent_03=repurposing_brief_from_agent_03,
        )
        package_obj, generation = run_agent(raw_input, provider_mode=provider_mode)
        package = _package_to_dict(package_obj)
    except UserFacingError as exc:
        raw_input = {}
        package = _serializable_error(str(exc))
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        raw_input = {}
        package = _serializable_error(
            "The live GCP/Vertex run could not start. Please set VERTEX_AI_PROJECT, "
            f"authenticate with Google ADC, and try again ({type(exc).__name__})."
        )

    record = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_mode": provider_mode,
        "source_type": (source_type or "raw_article_text").strip(),
        "input": raw_input,
        "generation": generation,
        "package": package,
    }
    _save_run(record)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def show_run(request: Request, run_id: str) -> HTMLResponse:
    record = _load_run(run_id)
    return templates.TemplateResponse(request, "result.html", _view_model(record))
