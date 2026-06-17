"""Prompt helpers for Agent 16."""

from __future__ import annotations

from digital_marketing.profiles import get_profile
from digital_marketing.prompts import build_generation_prompt, build_system_prompt

from .schemas import AdCopyCreationRequest


PROFILE = get_profile("agent-16")


def build_system(cfg: dict | None = None) -> str:
    _ = cfg
    return build_system_prompt(PROFILE)


def generation_prompt(request: AdCopyCreationRequest) -> str:
    return build_generation_prompt(PROFILE, request)


__all__ = ["PROFILE", "build_system", "generation_prompt"]
