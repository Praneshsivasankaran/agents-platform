"""Errors for Agent 14."""

from __future__ import annotations

from demand_generation.workflow import BillableNodeError


class Agent14Error(Exception):
    """Base Agent 14 error."""


__all__ = ["Agent14Error", "BillableNodeError"]