"""Errors for Agent 24."""

from __future__ import annotations

from marketing_operations.workflow import BillableNodeError


class agent24Error(Exception):
    """Base Agent 24 error."""


__all__ = ["agent24Error", "BillableNodeError"]
