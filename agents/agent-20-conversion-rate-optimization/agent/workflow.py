"""LangGraph workflow for Agent 20."""

from __future__ import annotations

from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from digital_marketing.workflow import build_graph as build_digital_marketing_graph

from .prompts import PROFILE
from .schemas import ConversionRateOptimizationPackage, ConversionRateOptimizationRequest


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 20's cloud-neutral LangGraph workflow."""
    return build_digital_marketing_graph(
        PROFILE,
        cfg,
        llm,
        tel,
        request_cls=ConversionRateOptimizationRequest,
        package_cls=ConversionRateOptimizationPackage,
    )


__all__ = ["build_graph"]
