"""FastAPI dependencies: session, repositories, use cases, and JWT principal."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.exceptions import AuthenticationError, AuthorizationError, DatabaseNotConfiguredError
from aegis.application.incidents import (
    CreateIncident,
    GetIncident,
    ListIncidents,
    TransitionIncident,
)
from aegis.application.incidents.ingest_signal import IngestIncidentSignal
from aegis.config.settings import Settings
from aegis.core.protocols import IncidentRepository
from aegis.domain.auth.enums import Role
from aegis.domain.auth.permissions import Permission, has_permission
from aegis.infrastructure.auth.jwt import (
    InvalidAccessTokenError,
    JwtNotConfiguredError,
    decode_access_token,
)
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated API caller (FR-070)."""

    subject: str
    role: Role


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


def get_ingest_incident_signal(
    repos: Repositories = Depends(get_repositories),
) -> IngestIncidentSignal:
    return IngestIncidentSignal(repos.incidents)


def get_get_incident(repos: Repositories = Depends(get_repositories)) -> GetIncident:
    return GetIncident(repos.incidents)


def get_list_incidents(repos: Repositories = Depends(get_repositories)) -> ListIncidents:
    return ListIncidents(repos.incidents)


def get_transition_incident(
    repos: Repositories = Depends(get_repositories),
) -> TransitionIncident:
    return TransitionIncident(repos.incidents)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Validate Bearer JWT (NFR-030)."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationError("Missing or invalid Authorization bearer token.")

    settings = _settings_from(request)
    try:
        payload = decode_access_token(settings, credentials.credentials)
    except JwtNotConfiguredError:
        raise
    except InvalidAccessTokenError as exc:
        raise AuthenticationError(str(exc)) from exc

    return CurrentUser(subject=payload.subject, role=payload.role)


def require_role(*allowed: Role) -> Callable[..., CurrentUser]:
    """Restrict a route to explicit roles (FR-071)."""

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise AuthorizationError("Insufficient role for this operation.")
        return user

    return _check


def require_permission(permission: Permission) -> Callable[..., CurrentUser]:
    """Restrict a route using the v0.2 permission matrix (FR-071)."""

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(user.role, permission):
            raise AuthorizationError("Insufficient role for this operation.")
        return user

    return _check


def _settings_from(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise JwtNotConfiguredError(
            "JWT is not configured. Set AEGIS_JWT_SECRET (never hardcode secrets)."
        )
    return settings
