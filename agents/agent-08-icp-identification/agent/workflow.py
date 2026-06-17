"""LangGraph workflow for Agent 08."""

from __future__ import annotations

from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from demand_generation.workflow import build_graph as build_demand_generation_graph

from .prompts import PROFILE
from .schemas import ICPIdentificationPackage, ICPIdentificationRequest


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 08's cloud-neutral LangGraph workflow."""
    return build_demand_generation_graph(
        PROFILE,
        cfg,
        llm,
        tel,
        request_cls=ICPIdentificationRequest,
        package_cls=ICPIdentificationPackage,
    )


__all__ = ["build_graph"]

