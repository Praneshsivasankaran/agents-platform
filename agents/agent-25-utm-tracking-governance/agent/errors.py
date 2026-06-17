"""Errors for Agent 25."""

from __future__ import annotations

from marketing_operations.workflow import BillableNodeError


class agent25Error(Exception):
    """Base Agent 25 error."""


__all__ = ["agent25Error", "BillableNodeError"]
