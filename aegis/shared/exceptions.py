"""Base exception hierarchy for AEGIS.

The API layer maps these to HTTP status codes later (Step 1.8).
"""


class DomainError(Exception):
    """Base error for AEGIS business and application failures."""


class NotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class ValidationError(DomainError):
    """Raised when input or domain state is invalid."""
