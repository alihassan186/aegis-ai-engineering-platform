"""Application settings for local, test, and production environments."""

from __future__ import annotations

import os
from dataclasses import dataclass

_ENVIRONMENT_NAMES = {"development", "test", "production"}
_ASYNC_POSTGRES_PREFIX = "postgresql+asyncpg://"


@dataclass(frozen=True)
class Settings:
    """Environment-aware settings container.

    Secrets and connection strings come from the process environment
    (NFR-032, THR-013). Never hardcode credentials here.
    """

    environment: str = "development"
    debug: bool = False
    app_name: str = "aegis"
    log_level: str = "INFO"
    database_url: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        environment = os.getenv("AEGIS_ENV", "development").lower()
        if environment not in _ENVIRONMENT_NAMES:
            environment = "development"

        database_url = os.getenv("AEGIS_DATABASE_URL", "").strip()
        if database_url and not database_url.startswith(_ASYNC_POSTGRES_PREFIX):
            raise ValueError(
                "AEGIS_DATABASE_URL must use the postgresql+asyncpg:// driver prefix (ADR-002)."
            )
        if environment == "production" and not database_url:
            raise ValueError("AEGIS_DATABASE_URL is required when AEGIS_ENV=production (NFR-060).")

        return cls(
            environment=environment,
            debug=os.getenv("AEGIS_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
            app_name=os.getenv("AEGIS_APP_NAME", "aegis"),
            log_level=os.getenv("AEGIS_LOG_LEVEL", "INFO").upper(),
            database_url=database_url,
        )


def get_settings() -> Settings:
    return Settings.from_env()
