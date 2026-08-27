"""Settings load from environment variables (NFR-032, NFR-060)."""

from __future__ import annotations

import pytest

from aegis.config.settings import Settings


def test_defaults_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AEGIS_ENV",
        "AEGIS_DEBUG",
        "AEGIS_APP_NAME",
        "AEGIS_LOG_LEVEL",
        "AEGIS_DATABASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.app_name == "aegis"
    assert settings.log_level == "INFO"
    assert settings.database_url == ""


def test_loads_database_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AEGIS_DATABASE_URL",
        "postgresql+asyncpg://aegis:aegis@127.0.0.1:5432/aegis",
    )
    monkeypatch.setenv("AEGIS_ENV", "development")

    settings = Settings.from_env()

    assert settings.database_url == "postgresql+asyncpg://aegis:aegis@127.0.0.1:5432/aegis"


def test_unknown_environment_falls_back_to_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_ENV", "staging")
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)

    settings = Settings.from_env()

    assert settings.environment == "development"


def test_debug_flag_parses_truthy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_DEBUG", "true")
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)

    assert Settings.from_env().debug is True


def test_test_environment_allows_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_ENV", "test")
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)

    settings = Settings.from_env()

    assert settings.environment == "test"
    assert settings.database_url == ""


def test_production_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_ENV", "production")
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="AEGIS_DATABASE_URL is required"):
        Settings.from_env()


def test_database_url_must_use_asyncpg_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_DATABASE_URL", "postgresql://aegis:aegis@127.0.0.1:5432/aegis")

    with pytest.raises(ValueError, match="postgresql\\+asyncpg://"):
        Settings.from_env()
