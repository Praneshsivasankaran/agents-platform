"""Controlled Agent 07 error types."""
from __future__ import annotations


class Agent07Error(Exception):
    """Base class for controlled Agent 07 failures."""


class InvalidCaseStudyInputError(Agent07Error):
    """Required case study context is empty or malformed."""


class CostCeilingExceededError(Agent07Error):
    """The configured request cost ceiling was exceeded or would be exceeded."""


class ModelOutputParseError(Agent07Error):
    """A provider response could not be parsed into the expected schema."""


class UnsafeClaimError(Agent07Error):
    """A hard-fail claim risk was detected."""
