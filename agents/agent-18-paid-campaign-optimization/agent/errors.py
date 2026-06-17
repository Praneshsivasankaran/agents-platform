"""Errors for Agent 18."""

from __future__ import annotations

from digital_marketing.workflow import BillableNodeError


class Agent18Error(Exception):
    """Base Agent 18 error."""


__all__ = ["Agent18Error", "BillableNodeError"]
