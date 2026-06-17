"""Errors for Agent 16."""

from __future__ import annotations

from digital_marketing.workflow import BillableNodeError


class Agent16Error(Exception):
    """Base Agent 16 error."""


__all__ = ["Agent16Error", "BillableNodeError"]
