"""Scoring wrapper for Agent 25."""

from __future__ import annotations

from marketing_operations.scoring import determine_quality_status, determine_terminal_status, score_quality

from .prompts import PROFILE

__all__ = ["PROFILE", "determine_quality_status", "determine_terminal_status", "score_quality"]
