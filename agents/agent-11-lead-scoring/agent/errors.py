"""Errors for Agent 11."""

from __future__ import annotations

from demand_generation.workflow import BillableNodeError


class Agent11Error(Exception):
    """Base Agent 11 error."""


__all__ = ["Agent11Error", "BillableNodeError"]