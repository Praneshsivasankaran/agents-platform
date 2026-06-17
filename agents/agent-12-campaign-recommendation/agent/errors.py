"""Errors for Agent 12."""

from __future__ import annotations

from demand_generation.workflow import BillableNodeError


class Agent12Error(Exception):
    """Base Agent 12 error."""


__all__ = ["Agent12Error", "BillableNodeError"]