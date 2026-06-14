"""Prompt helpers and trust boundaries for Agent 02.

Every source article/blog is untrusted data. Any instruction embedded in it is
content to transform, not an instruction to follow.
"""
from __future__ import annotations

from ._impl import (
    _AGENT_DATA_CLOSE,
    _AGENT_DATA_OPEN,
    _UNTRUSTED_CLOSE,
    _UNTRUSTED_OPEN,
    agent_data_block,
    build_system,
    factual_review_prompt,
    generation_prompt,
    review_prompt,
    revision_prompt,
    untrusted_block,
    user_context_block,
)

__all__ = [
    "_AGENT_DATA_CLOSE",
    "_AGENT_DATA_OPEN",
    "_UNTRUSTED_CLOSE",
    "_UNTRUSTED_OPEN",
    "agent_data_block",
    "build_system",
    "factual_review_prompt",
    "generation_prompt",
    "review_prompt",
    "revision_prompt",
    "untrusted_block",
    "user_context_block",
]
