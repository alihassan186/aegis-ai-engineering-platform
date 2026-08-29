"""Operational API errors (not domain rules)."""


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a route needs Postgres but no engine was configured."""
