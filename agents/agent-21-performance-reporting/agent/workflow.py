"""LangGraph workflow for Agent 21."""

from __future__ import annotations

from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from digital_marketing.workflow import build_graph as build_digital_marketing_graph

from .prompts import PROFILE
from .schemas import PerformanceReportingPackage, PerformanceReportingRequest


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 21's cloud-neutral LangGraph workflow."""
    return build_digital_marketing_graph(
        PROFILE,
        cfg,
        llm,
        tel,
        request_cls=PerformanceReportingRequest,
        package_cls=PerformanceReportingPackage,
    )


__all__ = ["build_graph"]
