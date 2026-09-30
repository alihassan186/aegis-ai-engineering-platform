"""Suite-wide pytest defaults. Loaded before test modules import the app."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from aegis.application.policy.cache import clear_policy_rule_cache

# Stop Settings.from_env() from reading the developer `.env` during tests.
os.environ["AEGIS_SKIP_DOTENV"] = "1"
os.environ["SIMULATOR_SKIP_DOTENV"] = "1"


@pytest.fixture(autouse=True)
def _reset_policy_rule_cache() -> Iterator[None]:
    clear_policy_rule_cache()
    yield
    clear_policy_rule_cache()
