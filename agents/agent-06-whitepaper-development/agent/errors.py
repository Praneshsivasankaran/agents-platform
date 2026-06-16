"""Agent 06 error types."""


class Agent06Error(Exception):
    """Base error for Agent 06."""


class Agent06ValidationError(Agent06Error):
    """Raised for user-fixable validation errors."""
