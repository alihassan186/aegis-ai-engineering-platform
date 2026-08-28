"""Alembic environment — async PostgreSQL (ADR-002, NFR-061)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from aegis.config.settings import get_settings
from aegis.infrastructure.database import models as _models  # noqa: F401
from aegis.infrastructure.database.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_LOCAL_DATABASE_URL = "postgresql+asyncpg://aegis:aegis@127.0.0.1:5434/aegis"


def _database_url() -> str:
    settings_url = get_settings().database_url
    if settings_url:
        return settings_url
    ini_url = config.get_main_option("sqlalchemy.url", "")
    if ini_url and not ini_url.startswith("driver://"):
        return ini_url
    return _LOCAL_DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
