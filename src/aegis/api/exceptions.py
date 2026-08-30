"""Operational API errors (not domain rules)."""


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a route needs Postgres but no engine was configured."""


class AuthenticationError(Exception):
    """Missing or invalid credentials (HTTP 401)."""


class AuthorizationError(Exception):
    """Authenticated caller lacks permission (HTTP 403)."""
