"""Engine factory rejects a missing database URL."""

from __future__ import annotations

import pytest

from aegis.config.settings import Settings
from aegis.infrastructure.database.session import create_db_engine


def test_create_db_engine_requires_database_url() -> None:
    settings = Settings(environment="test", database_url="")

    with pytest.raises(ValueError, match="AEGIS_DATABASE_URL is required"):
        create_db_engine(settings)
