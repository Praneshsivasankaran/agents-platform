"""Prompt helpers for Agent 10."""

from __future__ import annotations

from demand_generation.profiles import get_profile
from demand_generation.prompts import build_generation_prompt, build_system_prompt

from .schemas import LeadGenerationRequest


PROFILE = get_profile("agent-10")


def build_system(cfg: dict | None = None) -> str:
    _ = cfg
    return build_system_prompt(PROFILE)


def generation_prompt(request: LeadGenerationRequest) -> str:
    return build_generation_prompt(PROFILE, request)


__all__ = ["PROFILE", "build_system", "generation_prompt"]