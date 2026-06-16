"""Agent 04 error types."""
from __future__ import annotations


class Agent04InputError(ValueError):
    """Raised for safe, user-actionable request validation errors."""


class Agent04ProcessingError(RuntimeError):
    """Raised for sanitized processing failures."""
