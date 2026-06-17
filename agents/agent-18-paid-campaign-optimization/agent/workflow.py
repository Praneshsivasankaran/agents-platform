"""LangGraph workflow for Agent 18."""

from __future__ import annotations

from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from digital_marketing.workflow import build_graph as build_digital_marketing_graph

from .prompts import PROFILE
from .schemas import PaidCampaignOptimizationPackage, PaidCampaignOptimizationRequest


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 18's cloud-neutral LangGraph workflow."""
    return build_digital_marketing_graph(
        PROFILE,
        cfg,
        llm,
        tel,
        request_cls=PaidCampaignOptimizationRequest,
        package_cls=PaidCampaignOptimizationPackage,
    )


__all__ = ["build_graph"]
