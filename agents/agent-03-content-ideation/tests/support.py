"""Shared test fixtures for Agent 03."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.interfaces import LLMResponse
from core.interfaces.llm import Tier
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider

from agent.contracts import LLMIdeaBundle, LLMContentIdea


LLM_IDEA_SENTINEL = "briefspring"


def load_cfg() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "config" / "base.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def valid_campaign(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "campaign_goal": "Build awareness for an AI-assisted content planning product",
        "product_or_service": "ContentIQ",
        "target_audience": "B2B marketing managers at growing SaaS companies",
        "industry": "B2B SaaS",
        "brand_tone": "clear, practical, confident",
        "key_message": "AI agents turn campaign context into structured content ideas faster.",
        "optional_keywords": ["content planning", "AI agents", "campaign strategy"],
        "optional_content_type_preference": ["Blog", "LinkedIn post", "Newsletter"],
        "optional_notes": "The team wants practical angles and proof placeholders.",
        "optional_constraints": ["Avoid unsupported percentage claims", "Avoid heavy jargon"],
        "number_of_ideas": 8,
    }
    data.update(overrides)
    return data


class ScriptedIdeationLLM(MockLLMProvider):
    """Returns a usable structured idea bundle for Agent 03 generation tests."""

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        if response_schema is LLMIdeaBundle:
            raw = (
                (
                    f"{LLM_IDEA_SENTINEL}: the campaign brief audit for SaaS teams",
                    "Turn the campaign input into a checklist that reveals missing audience and proof details.",
                    "Show how a short audit helps marketers improve the brief before writing starts.",
                    "Blog",
                ),
                (
                    f"{LLM_IDEA_SENTINEL}: one message into four content paths",
                    "Map the same key message into blog, newsletter, social, and short-video directions.",
                    "Show the workflow that keeps every format aligned without copying the same wording.",
                    "Newsletter",
                ),
                (
                    f"{LLM_IDEA_SENTINEL}: proof placeholders before bold claims",
                    "Explain how teams can mark evidence gaps before downstream agents draft content.",
                    "Use a safety-led angle that keeps campaign claims review-ready and credible.",
                    "LinkedIn post",
                ),
                (
                    f"{LLM_IDEA_SENTINEL}: audience objections as content prompts",
                    "Turn likely objections from marketers into useful idea angles and CTAs.",
                    "Frame objections as the starting point for more specific campaign content.",
                    "Short Video",
                ),
            )
            ideas = tuple(
                LLMContentIdea(
                    title=title,
                    description=description,
                    angle=angle,
                    recommended_format=format_name,
                    funnel_stage="awareness",
                    audience_fit_reason="B2B marketers need a repeatable way to move from context to drafts.",
                    originality_note="Uses only the supplied campaign brief and explicit proof placeholders.",
                )
                for title, description, angle, format_name in raw
            )
            usage = Usage(prompt_tokens=64, completion_tokens=128, synthetic=True)
            return LLMResponse.structured_from(
                LLMIdeaBundle,
                LLMIdeaBundle(ideas=ideas).model_dump(),
                usage=usage,
            )
        return super().respond(
            messages,
            tier=tier,
            params=params,
            tools=tools,
            response_schema=response_schema,
        )
