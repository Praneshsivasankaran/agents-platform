"""Errors for Agent 26."""

from __future__ import annotations

from marketing_operations.workflow import BillableNodeError


class agent26Error(Exception):
    """Base Agent 26 error."""


__all__ = ["agent26Error", "BillableNodeError"]
