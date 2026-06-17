"""Errors for Agent 20."""

from __future__ import annotations

from digital_marketing.workflow import BillableNodeError


class Agent20Error(Exception):
    """Base Agent 20 error."""


__all__ = ["Agent20Error", "BillableNodeError"]
