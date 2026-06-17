"""Errors for Agent 10."""

from __future__ import annotations

from demand_generation.workflow import BillableNodeError


class Agent10Error(Exception):
    """Base Agent 10 error."""


__all__ = ["Agent10Error", "BillableNodeError"]