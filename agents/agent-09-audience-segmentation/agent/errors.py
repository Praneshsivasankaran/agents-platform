"""Errors for Agent 09."""

from __future__ import annotations

from demand_generation.workflow import BillableNodeError


class Agent09Error(Exception):
    """Base Agent 09 error."""


__all__ = ["Agent09Error", "BillableNodeError"]