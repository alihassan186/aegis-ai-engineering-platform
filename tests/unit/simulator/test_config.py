"""Simulator settings load from the environment."""

from __future__ import annotations

import pytest

from apps.simulator.config import Settings
from apps.simulator.scenarios.catalog import ScenarioId


def test_defaults_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SIMULATOR_ENV",
        "SIMULATOR_DEBUG",
        "SIMULATOR_APP_NAME",
        "SIMULATOR_LOG_LEVEL",
        "SIMULATOR_HOST",
        "SIMULATOR_PORT",
        "AEGIS_BASE_URL",
        "SIMULATOR_SCENARIO",
        "SIMULATOR_WEBHOOK_SECRET",
        "AEGIS_WEBHOOK_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SIMULATOR_SKIP_DOTENV", "1")

    settings = Settings.from_env()

    assert settings.environment == "development"
    assert settings.app_name == "simulator"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8001
    assert settings.aegis_base_url == ""
    assert settings.scenario is None
    assert settings.webhook_secret == ""


def test_loads_port_and_aegis_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATOR_SKIP_DOTENV", "1")
    monkeypatch.setenv("SIMULATOR_PORT", "9001")
    monkeypatch.setenv("AEGIS_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("SIMULATOR_SCENARIO", "latency_spike")

    settings = Settings.from_env()

    assert settings.port == 9001
    assert settings.aegis_base_url == "http://127.0.0.1:8000"
    assert settings.scenario is ScenarioId.LATENCY_SPIKE
    assert settings.webhook_secret == ""


def test_simulator_webhook_secret_falls_back_to_aegis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMULATOR_SKIP_DOTENV", "1")
    monkeypatch.delenv("SIMULATOR_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("AEGIS_WEBHOOK_SECRET", "shared-webhook-secret")

    settings = Settings.from_env()

    assert settings.webhook_secret == "shared-webhook-secret"
