"""Application settings for local, test, and production environments."""

from __future__ import annotations

import os
from dataclasses import dataclass

_ENVIRONMENT_NAMES = {"development", "test", "production"}


@dataclass(frozen=True)
class Settings:
    """Minimal environment-aware settings container."""

    environment: str = "development"
    debug: bool = False
    app_name: str = "aegis"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        environment = os.getenv("AEGIS_ENV", "development").lower()
        if environment not in _ENVIRONMENT_NAMES:
            environment = "development"

        return cls(
            environment=environment,
            debug=os.getenv("AEGIS_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
            app_name=os.getenv("AEGIS_APP_NAME", "aegis"),
            log_level=os.getenv("AEGIS_LOG_LEVEL", "INFO").upper(),
        )


def get_settings() -> Settings:
    return Settings.from_env()
