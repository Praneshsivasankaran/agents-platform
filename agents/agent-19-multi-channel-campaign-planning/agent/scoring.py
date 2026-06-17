"""Scoring wrapper for Agent 19."""

from __future__ import annotations

from digital_marketing.scoring import determine_quality_status, determine_terminal_status, score_quality

from .prompts import PROFILE

__all__ = ["PROFILE", "determine_quality_status", "determine_terminal_status", "score_quality"]
