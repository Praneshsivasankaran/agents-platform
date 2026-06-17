"""LangGraph workflow for Agent 23."""

from __future__ import annotations

from typing import Any

from core.interfaces import Telemetry
from core.interfaces.llm import LLMProvider
from marketing_operations.workflow import build_graph as build_marketing_operations_graph

from .prompts import PROFILE
from .schemas import MarketingAutomationWorkflowDesignPackage, MarketingAutomationWorkflowDesignRequest


def build_graph(cfg: dict, llm: LLMProvider, tel: Telemetry) -> Any:
    """Compile Agent 23's cloud-neutral LangGraph workflow."""
    return build_marketing_operations_graph(
        PROFILE,
        cfg,
        llm,
        tel,
        request_cls=MarketingAutomationWorkflowDesignRequest,
        package_cls=MarketingAutomationWorkflowDesignPackage,
    )


__all__ = ["build_graph"]
