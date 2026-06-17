"""Errors for Agent 21."""

from __future__ import annotations

from digital_marketing.workflow import BillableNodeError


class Agent21Error(Exception):
    """Base Agent 21 error."""


__all__ = ["Agent21Error", "BillableNodeError"]
