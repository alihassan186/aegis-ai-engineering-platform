"""Operational API errors (not domain rules)."""


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a route needs Postgres but no engine was configured."""


class AuthenticationError(Exception):
    """Missing or invalid credentials (HTTP 401)."""

    def __init__(self, message: str, *, challenge: str | None = "Bearer") -> None:
        super().__init__(message)
        self.challenge = challenge


class WebhookNotConfiguredError(RuntimeError):
    """Raised when AEGIS_WEBHOOK_SECRET is missing."""


class AuthorizationError(Exception):
    """Authenticated caller lacks permission (HTTP 403)."""
