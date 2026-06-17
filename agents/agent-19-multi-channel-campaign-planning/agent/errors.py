"""Errors for Agent 19."""

from __future__ import annotations

from digital_marketing.workflow import BillableNodeError


class Agent19Error(Exception):
    """Base Agent 19 error."""


__all__ = ["Agent19Error", "BillableNodeError"]
