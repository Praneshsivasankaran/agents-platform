"""Errors for Agent 23."""

from __future__ import annotations

from marketing_operations.workflow import BillableNodeError


class agent23Error(Exception):
    """Base Agent 23 error."""


__all__ = ["agent23Error", "BillableNodeError"]
