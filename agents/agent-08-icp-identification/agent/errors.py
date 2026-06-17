"""Errors for Agent 08."""

from __future__ import annotations

from demand_generation.workflow import BillableNodeError


class Agent08Error(Exception):
    """Base Agent 08 error."""


__all__ = ["Agent08Error", "BillableNodeError"]

