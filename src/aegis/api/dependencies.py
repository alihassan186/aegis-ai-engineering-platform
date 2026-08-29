"""FastAPI dependencies: session, repositories, use cases."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.exceptions import DatabaseNotConfiguredError
from aegis.application.incidents import (
    CreateIncident,
    GetIncident,
    ListIncidents,
    TransitionIncident,
)
from aegis.core.protocols import IncidentRepository
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    incidents: IncidentRepository


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request: commit on success, rollback on error."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise DatabaseNotConfiguredError(
            "Database is not configured. Copy config/.env.example to .env "
            "and set AEGIS_DATABASE_URL (Postgres must be running)."
        )

    session: AsyncSession = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_repositories(session: AsyncSession = Depends(get_db)) -> Repositories:
    return Repositories(incidents=SqlAlchemyIncidentRepository(session))


def get_create_incident(repos: Repositories = Depends(get_repositories)) -> CreateIncident:
    return CreateIncident(repos.incidents)


def get_get_incident(repos: Repositories = Depends(get_repositories)) -> GetIncident:
    return GetIncident(repos.incidents)


def get_list_incidents(repos: Repositories = Depends(get_repositories)) -> ListIncidents:
    return ListIncidents(repos.incidents)


def get_transition_incident(
    repos: Repositories = Depends(get_repositories),
) -> TransitionIncident:
    return TransitionIncident(repos.incidents)
