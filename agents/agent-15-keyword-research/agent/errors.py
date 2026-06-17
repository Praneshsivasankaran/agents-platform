"""Errors for Agent 15."""

from __future__ import annotations

from digital_marketing.workflow import BillableNodeError


class Agent15Error(Exception):
    """Base Agent 15 error."""


__all__ = ["Agent15Error", "BillableNodeError"]
