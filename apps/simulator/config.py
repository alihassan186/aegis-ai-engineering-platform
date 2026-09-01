"""Simulator process settings. Independent of ``aegis.config`` (ADR-001)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from apps.simulator.scenarios.catalog import ScenarioId

_ENVIRONMENT_NAMES = {"development", "test", "production"}
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv_file() -> None:
    """Load repo-root ``.env`` without overriding existing vars.

    Tests set ``SIMULATOR_SKIP_DOTENV=1`` (and usually ``AEGIS_SKIP_DOTENV=1``).
    """
    if os.getenv("SIMULATOR_SKIP_DOTENV") == "1":
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
    """Env-backed settings. No secrets hardcoded (THR-013).

    ``aegis_base_url`` is reserved for Step 2.5. This step must not call AEGIS.
    """

    environment: str = "development"
    debug: bool = False
    app_name: str = "simulator"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8001
    aegis_base_url: str = ""
    scenario: ScenarioId | None = None

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv_file()
        environment = os.getenv("SIMULATOR_ENV", "development").lower()
        if environment not in _ENVIRONMENT_NAMES:
            environment = "development"

        return cls(
            environment=environment,
            debug=os.getenv("SIMULATOR_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
            app_name=os.getenv("SIMULATOR_APP_NAME", "simulator"),
            log_level=os.getenv("SIMULATOR_LOG_LEVEL", "INFO").upper(),
            host=os.getenv("SIMULATOR_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_parse_positive_int(os.getenv("SIMULATOR_PORT"), default=8001),
            aegis_base_url=os.getenv("AEGIS_BASE_URL", "").strip(),
            scenario=_parse_optional_scenario(os.getenv("SIMULATOR_SCENARIO")),
        )


def get_settings() -> Settings:
    return Settings.from_env()


def _parse_optional_scenario(raw: str | None) -> ScenarioId | None:
    if raw is None or not raw.strip():
        return None
    try:
        return ScenarioId(raw.strip())
    except ValueError:
        return None


def _parse_positive_int(raw: str | None, *, default: int) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default
