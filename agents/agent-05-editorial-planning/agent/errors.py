"""Agent 05 error types."""
from __future__ import annotations


class Agent05InputError(ValueError):
    """Raised for safe, user-actionable request validation errors."""


class Agent05ProcessingError(RuntimeError):
    """Raised for sanitized processing failures."""

