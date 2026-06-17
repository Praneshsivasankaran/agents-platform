"""Prompt helpers for Agent 23."""

from __future__ import annotations

from marketing_operations.profiles import get_profile
from marketing_operations.prompts import build_generation_prompt, build_system_prompt

from .schemas import MarketingAutomationWorkflowDesignRequest


PROFILE = get_profile("agent-23")


def build_system(cfg: dict | None = None) -> str:
    _ = cfg
    return build_system_prompt(PROFILE)


def generation_prompt(request: MarketingAutomationWorkflowDesignRequest) -> str:
    return build_generation_prompt(PROFILE, request)


__all__ = ["PROFILE", "build_system", "generation_prompt"]
