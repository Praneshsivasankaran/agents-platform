"""Errors for Agent 28."""

from __future__ import annotations

from marketing_operations.workflow import BillableNodeError


class agent28Error(Exception):
    """Base Agent 28 error."""


__all__ = ["agent28Error", "BillableNodeError"]
