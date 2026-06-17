"""Errors for Agent 13."""

from __future__ import annotations

from demand_generation.workflow import BillableNodeError


class Agent13Error(Exception):
    """Base Agent 13 error."""


__all__ = ["Agent13Error", "BillableNodeError"]