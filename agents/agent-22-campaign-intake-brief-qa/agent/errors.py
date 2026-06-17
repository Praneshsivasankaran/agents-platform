"""Errors for Agent 22."""

from __future__ import annotations

from marketing_operations.workflow import BillableNodeError


class agent22Error(Exception):
    """Base Agent 22 error."""


__all__ = ["agent22Error", "BillableNodeError"]
