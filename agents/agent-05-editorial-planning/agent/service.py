"""Service helpers for running Agent 05 from config."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.factory import get_llm_provider, get_object_storage, get_secret_store, get_telemetry

from .workflow import build_graph


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else Path(__file__).parents[1] / "config" / "base.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def build_service_graph(cfg: dict[str, Any] | None = None):
    resolved = cfg or load_config()
    # Resolve shared abstractions here so config-only provider selection is exercised
    # without leaking provider details into agent workflow code.
    secret_store = get_secret_store(resolved)
    _ = get_object_storage(resolved, secret_store=secret_store)
    llm = get_llm_provider(resolved, secret_store=secret_store)
    tel = get_telemetry(resolved)
    return build_graph(resolved, llm, tel)


def run(request: dict[str, Any], cfg: dict[str, Any] | None = None):
    graph = build_service_graph(cfg)
    result = graph.invoke({"raw_input": request})
    return result["final_output"]

