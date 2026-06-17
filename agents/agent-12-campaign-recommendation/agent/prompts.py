"""Prompt helpers for Agent 12."""

from __future__ import annotations

from demand_generation.profiles import get_profile
from demand_generation.prompts import build_generation_prompt, build_system_prompt

from .schemas import CampaignRecommendationRequest


PROFILE = get_profile("agent-12")


def build_system(cfg: dict | None = None) -> str:
    _ = cfg
    return build_system_prompt(PROFILE)


def generation_prompt(request: CampaignRecommendationRequest) -> str:
    return build_generation_prompt(PROFILE, request)


__all__ = ["PROFILE", "build_system", "generation_prompt"]