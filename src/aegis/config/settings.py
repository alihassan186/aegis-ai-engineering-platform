"""Application settings for local, test, and production environments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ENVIRONMENT_NAMES = {"development", "test", "production"}
_ASYNC_POSTGRES_PREFIX = "postgresql+asyncpg://"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv_file() -> None:
    """Load repo-root `.env` into os.environ without overriding existing vars.

    Uvicorn does not read `.env` by itself. Tests set AEGIS_SKIP_DOTENV=1 so
    fixtures stay in control of the environment.
    """
    if os.getenv("AEGIS_SKIP_DOTENV") == "1":
        return
    path = _REPO_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


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
    jwt_secret: str = ""
    jwt_expire_seconds: int = 3600

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv_file()
        environment = os.getenv("AEGIS_ENV", "development").lower()
        if environment not in _ENVIRONMENT_NAMES:
            environment = "development"

        database_url = os.getenv("AEGIS_DATABASE_URL", "").strip()
        if database_url and not database_url.startswith(_ASYNC_POSTGRES_PREFIX):
            raise ValueError(
                "AEGIS_DATABASE_URL must use the postgresql+asyncpg:// driver prefix (ADR-002)."
            )
        jwt_secret = os.getenv("AEGIS_JWT_SECRET", "").strip()
        jwt_expire_seconds = _parse_positive_int(
            os.getenv("AEGIS_JWT_EXPIRE_SECONDS"),
            default=3600,
        )

        if environment == "production" and not database_url:
            raise ValueError("AEGIS_DATABASE_URL is required when AEGIS_ENV=production (NFR-060).")
        if environment == "production" and not jwt_secret:
            raise ValueError("AEGIS_JWT_SECRET is required when AEGIS_ENV=production (THR-013).")

        return cls(
            environment=environment,
            debug=os.getenv("AEGIS_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
            app_name=os.getenv("AEGIS_APP_NAME", "aegis"),
            log_level=os.getenv("AEGIS_LOG_LEVEL", "INFO").upper(),
            database_url=database_url,
            jwt_secret=jwt_secret,
            jwt_expire_seconds=jwt_expire_seconds,
        )


def get_settings() -> Settings:
    return Settings.from_env()


def _parse_positive_int(raw: str | None, *, default: int) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default
