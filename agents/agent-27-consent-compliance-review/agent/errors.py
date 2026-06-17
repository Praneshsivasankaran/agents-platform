"""Errors for Agent 27."""

from __future__ import annotations

from marketing_operations.workflow import BillableNodeError


class agent27Error(Exception):
    """Base Agent 27 error."""


__all__ = ["agent27Error", "BillableNodeError"]
