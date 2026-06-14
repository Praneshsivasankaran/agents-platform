"""Shared test/eval doubles for Agent 02.

``ScriptedRepurposerLLM`` returns a deterministic, gate-passing, source-safe
``LLMDraftBundle`` for the draft-generation/revision stages so offline tests can
exercise the real "parse LLM structured output -> build drafts" path (not the
template fallback). Every body/hook carries ``LLM_DRAFT_SENTINEL`` so a test can
assert the LLM payload actually reached the final package.

The scripted copy intentionally avoids statistics, claim trigger words
(study/report/customer/guarantee/proven), publishing verbs, injection phrases,
and generic-marketing phrases so it passes the deterministic factual/usefulness/
platform validators — proving the validators accept genuine LLM content while
still failing generic content (see the generic-LLM test).
"""
from __future__ import annotations

from typing import Any

from core.interfaces import BillableProviderError, LLMResponse
from core.interfaces.llm import Tier
from core.interfaces.usage import Usage
from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.schemas import LLMDraftBundle, LLMPlatformDraft, Platform

LLM_DRAFT_SENTINEL = "channelcraft"


def scripted_bundle() -> LLMDraftBundle:
    """A complete, gate-passing four-platform draft bundle authored by the 'model'."""
    return LLMDraftBundle(
        drafts=(
            LLMPlatformDraft(
                platform="linkedin",
                hook="channelcraft turns one approved guide into a sharper professional point of view.",
                body=(
                    "channelcraft starts from the approved source and keeps its meaning intact. "
                    "Many teams write strong long-form material and then let it sit unused. The "
                    "better move is to pull the single idea that helps a specific reader, explain "
                    "why it matters to them, and adapt the shape for the channel they actually "
                    "read. For decision makers on this network that means a clear stance, one "
                    "concrete takeaway they can apply this week, and a reason to open the full "
                    "source. Keep the wording specific to the source, drop the filler, and make "
                    "the reader feel the draft was built for their work rather than reused across "
                    "every channel. A reviewer can then check each idea against the source before "
                    "anyone shares it."
                ),
                cta="Open the approved source and decide which idea to apply first.",
                hashtags=("#contentstrategy", "#b2bmarketing", "#repurposing"),
                why_this_works="It gives a professional reader one specific stance and a concrete next action.",
                audience_value="Decision makers get a clear, source-grounded reason to act.",
            ),
            LLMPlatformDraft(
                platform="instagram",
                hook="channelcraft makes one idea easy to see and easy to skim.",
                body=(
                    "channelcraft keeps the caption visual and short. Lead with the one idea that "
                    "helps the reader, show it with a simple frame, and keep the lines easy to skim "
                    "on a phone. Pull a single takeaway from the source, pair it with a clear "
                    "visual angle, and close with one action the reader can take next. Drop the "
                    "filler and make every line earn its place so the caption feels designed for "
                    "this feed rather than reused from a long article."
                ),
                cta="Save this and open the full source when you plan your week.",
                hashtags=(
                    "#contentmarketing",
                    "#socialmedia",
                    "#marketingstrategy",
                    "#repurposing",
                    "#creators",
                    "#contentcreation",
                ),
                visual_angle="Carousel frames: source idea, why it matters, one clear action.",
                why_this_works="It gives a skimmable visual angle and one clear action for the feed.",
                audience_value="Followers get a quick, visual reason the idea matters to them.",
            ),
            LLMPlatformDraft(
                platform="x_twitter",
                hook="channelcraft breaks one idea into a tight, non-repeating thread.",
                thread_posts=(
                    "channelcraft turns one approved source into a short thread that respects the reader's time.",
                    "Begin with the single idea worth their attention and say why it matters to them specifically.",
                    "Add one concrete takeaway they can apply without reading the whole source first.",
                    "Show how the same idea changes shape for a feed, a caption, and a short script.",
                    "Close by pointing back to the approved source so a reviewer can verify before sharing.",
                ),
                cta="Read the approved source before adapting this thread.",
                why_this_works="Each post adds a new point without repeating the same sentence shape.",
                audience_value="Skimmers get sequential value instead of one padded update.",
            ),
            LLMPlatformDraft(
                platform="short_video",
                hook="channelcraft scripts a short video with a hook in the first three seconds.",
                voiceover=(
                    "channelcraft takes the approved idea and opens with a hook in the first three "
                    "seconds, then shows why the idea matters, gives one takeaway, and ends by "
                    "pointing back to the full source for review."
                ),
                scene_directions=(
                    "0-3s: bold on-screen hook over the source title.",
                    "4-20s: narrate the single strongest idea.",
                    "21-45s: show the idea adapting across channels.",
                    "46-60s: close on the call to review the source.",
                ),
                on_screen_text=("Approved source", "One clear idea", "Built per channel", "Review before sharing"),
                cta="Review the full source before turning this script into a video.",
                why_this_works="It opens with a three-second hook and includes scene flow, voiceover, and on-screen text.",
                audience_value="Viewers get a fast, structured reason the idea matters.",
            ),
        )
    )


class ScriptedRepurposerLLM(MockLLMProvider):
    """Returns ``scripted_bundle()`` for ``LLMDraftBundle`` requests; otherwise the base mock."""

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        if response_schema is LLMDraftBundle:
            usage = Usage(prompt_tokens=64, completion_tokens=128, synthetic=True)
            return LLMResponse.structured_from(
                LLMDraftBundle, scripted_bundle().model_dump(), usage=usage
            )
        return super().respond(
            messages, tier=tier, params=params, tools=tools, response_schema=response_schema
        )


class GenericLLM(MockLLMProvider):
    """Returns generic, low-value drafts so the deterministic gate must still fail them."""

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        if response_schema is LLMDraftBundle:
            usage = Usage(prompt_tokens=64, completion_tokens=64, synthetic=True)
            generic_body = (
                "channelcraft is a game changer that will unlock growth and transform your "
                "business in today's fast-paced world across every single channel you run."
            )
            generic_platforms: tuple[Platform, ...] = (
                "linkedin",
                "instagram",
                "x_twitter",
                "short_video",
            )
            drafts = tuple(
                LLMPlatformDraft(
                    platform=platform,
                    hook="channelcraft is a game changer for everyone everywhere.",
                    body=generic_body,
                    cta="Learn more.",
                    why_this_works="It is generic filler that should not pass the quality gate.",
                    audience_value="Anyone, supposedly.",
                )
                for platform in generic_platforms
            )
            return LLMResponse.structured_from(
                LLMDraftBundle, LLMDraftBundle(drafts=drafts).model_dump(), usage=usage
            )
        return super().respond(
            messages, tier=tier, params=params, tools=tools, response_schema=response_schema
        )


class TextOnlyLLM(MockLLMProvider):
    """Ignores the response_schema and returns plain text (structured is None) -> safe fallback."""

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        usage = Usage(prompt_tokens=32, completion_tokens=8, synthetic=True)
        return LLMResponse(text="[text-only] no structured payload", usage=usage)


class FactualReviewHiccupLLM(ScriptedRepurposerLLM):
    """Succeeds on structured (generate/revise) calls but raises a billable provider failure on the
    text (factual/review) calls — to prove a hiccup in a discarded-response stage does not block the
    deterministic validators or fail the run (and that incurred cost is preserved)."""

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        if response_schema is None:  # factual / review text calls
            raise BillableProviderError(
                Usage(
                    prompt_tokens=8,
                    completion_tokens=0,
                    cost_native=0.05,
                    currency="USD",
                    synthetic=False,
                ),
                "response_empty",
            )
        return super().respond(
            messages, tier=tier, params=params, tools=tools, response_schema=response_schema
        )


class CapturingTelemetry(StdoutTelemetry):
    """Records every log event so tests can assert provider-hiccup / fell_back telemetry."""

    def __init__(self, service: str = "agent02-test") -> None:
        super().__init__(service=service)
        self.events: list[tuple[str, dict[str, Any]]] = []

    def log(self, msg: str, **fields: Any) -> None:
        self.events.append((msg, dict(fields)))
        super().log(msg, **fields)
