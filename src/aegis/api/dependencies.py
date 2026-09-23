"""FastAPI dependencies: session, repositories, use cases, and JWT principal."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.event_publish import RequestEventBuffer, flush_pending_domain_events
from aegis.api.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DatabaseNotConfiguredError,
    OpenSearchNotConfiguredError,
)
from aegis.application.evidence.record_evidence import RecordEvidence
from aegis.application.incidents import (
    CreateIncident,
    GetIncident,
    ListIncidents,
    TransitionIncident,
)
from aegis.application.incidents.ingest_signal import IngestIncidentSignal
from aegis.application.investigation.control import ControlInvestigation
from aegis.application.investigation.get_progress import GetInvestigationProgress
from aegis.application.investigation.transition_rca import TransitionRca
from aegis.application.notifications.notify import NotifyInvestigation
from aegis.application.rag.retrieve import RetrieveKnowledge
from aegis.application.reports.build_post_incident import BuildPostIncidentReport
from aegis.config.settings import Settings
from aegis.core.protocols import (
    EvidenceRepository,
    IncidentRepository,
    InvestigationProgressRepository,
    NotificationRepository,
    RcaRepository,
)
from aegis.domain.auth.enums import Role
from aegis.domain.auth.permissions import Permission, has_permission
from aegis.infrastructure.auth.jwt import (
    InvalidAccessTokenError,
    JwtNotConfiguredError,
    decode_access_token,
)
from aegis.infrastructure.notifications.log_notifier import LogNotifier
from aegis.infrastructure.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository
from aegis.infrastructure.repositories.investigation_repository import (
    SqlAlchemyInvestigationProgressRepository,
)
from aegis.infrastructure.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from aegis.infrastructure.repositories.rca_repository import SqlAlchemyRcaRepository

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated API caller (FR-070)."""

    subject: str
    role: Role


@dataclass(frozen=True, slots=True)
class Repositories:
    incidents: IncidentRepository
    evidence: EvidenceRepository
    rca: RcaRepository
    progress: InvestigationProgressRepository
    notifications: NotificationRepository


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request: commit on success, rollback on error."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise DatabaseNotConfiguredError(
            "Database is not configured. Copy config/.env.example to .env "
            "and set AEGIS_DATABASE_URL (Postgres must be running)."
        )

    session: AsyncSession = factory()
    request.state.event_buffer = RequestEventBuffer()
    try:
        yield session
        await session.commit()
        flush_pending_domain_events(
            request.state.event_buffer,
            getattr(request.app.state, "event_publisher", None),
        )
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_repositories(session: AsyncSession = Depends(get_db)) -> Repositories:
    return Repositories(
        incidents=SqlAlchemyIncidentRepository(session),
        evidence=SqlAlchemyEvidenceRepository(session),
        rca=SqlAlchemyRcaRepository(session),
        progress=SqlAlchemyInvestigationProgressRepository(session),
        notifications=SqlAlchemyNotificationRepository(session),
    )


def _request_publisher(request: Request) -> RequestEventBuffer | None:
    buffer = getattr(request.state, "event_buffer", None)
    return buffer if isinstance(buffer, RequestEventBuffer) else None


def get_create_incident(
    request: Request,
    repos: Repositories = Depends(get_repositories),
) -> CreateIncident:
    return CreateIncident(repos.incidents, publisher=_request_publisher(request))


def get_ingest_incident_signal(
    request: Request,
    repos: Repositories = Depends(get_repositories),
) -> IngestIncidentSignal:
    return IngestIncidentSignal(repos.incidents, publisher=_request_publisher(request))


def get_get_incident(repos: Repositories = Depends(get_repositories)) -> GetIncident:
    return GetIncident(repos.incidents)


def get_list_incidents(repos: Repositories = Depends(get_repositories)) -> ListIncidents:
    return ListIncidents(repos.incidents)


def get_transition_incident(
    repos: Repositories = Depends(get_repositories),
) -> TransitionIncident:
    return TransitionIncident(repos.incidents)


def get_investigation_progress(
    repos: Repositories = Depends(get_repositories),
) -> GetInvestigationProgress:
    return GetInvestigationProgress(repos.incidents, repos.evidence, repos.rca, repos.progress)


def get_transition_rca(
    repos: Repositories = Depends(get_repositories),
) -> TransitionRca:
    reader = GetInvestigationProgress(repos.incidents, repos.evidence, repos.rca, repos.progress)
    notify = NotifyInvestigation(repos.notifications, LogNotifier())
    return TransitionRca(repos.incidents, repos.rca, repos.progress, reader, notify=notify)


def get_control_investigation(
    repos: Repositories = Depends(get_repositories),
) -> ControlInvestigation:
    reader = GetInvestigationProgress(repos.incidents, repos.evidence, repos.rca, repos.progress)
    return ControlInvestigation(repos.incidents, repos.progress, reader)


def get_record_evidence(
    repos: Repositories = Depends(get_repositories),
) -> RecordEvidence:
    return RecordEvidence(repos.evidence)


def get_build_report(
    repos: Repositories = Depends(get_repositories),
) -> BuildPostIncidentReport:
    return BuildPostIncidentReport(
        repos.incidents,
        repos.evidence,
        repos.rca,
        repos.progress,
        repos.notifications,
    )


def get_retrieve_knowledge(request: Request) -> RetrieveKnowledge:
    """Compose retrieve from app.state (wired in ``create_app``). No HMAC."""
    store = getattr(request.app.state, "knowledge_store", None)
    embedder = getattr(request.app.state, "embedder", None)
    if store is None or embedder is None:
        raise OpenSearchNotConfiguredError(
            "OpenSearch is not configured. Set AEGIS_OPENSEARCH_URL and ingest the "
            "knowledge corpus (uv run python -m aegis.rag.ingest)."
        )
    return RetrieveKnowledge(embedder=embedder, store=store)


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
