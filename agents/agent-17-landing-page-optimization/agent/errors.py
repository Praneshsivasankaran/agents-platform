"""Errors for Agent 17."""

from __future__ import annotations

from digital_marketing.workflow import BillableNodeError


class Agent17Error(Exception):
    """Base Agent 17 error."""


__all__ = ["Agent17Error", "BillableNodeError"]
