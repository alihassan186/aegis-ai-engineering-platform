"""Persisted notification row. Product event, not worker stdout."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from aegis.domain.notifications.enums import NotificationKind
from aegis.shared.exceptions import ValidationError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(moment: datetime, field_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValidationError(f"{field_name} must be timezone-aware.")
    return moment


def _require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field_name} must not be empty.")
    return cleaned


class Notification:
    """One notify attempt's durable record (FR-027 / FR-028)."""

    def __init__(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        kind: NotificationKind,
        event_type: str,
        reason: str,
        severity: str,
        service: str,
        link: str,
        dedupe_key: str,
        rca_version: int | None,
        created_at: datetime,
    ) -> None:
        if incident_id is None:
            raise ValidationError("incident_id is required.")
        self._id = id
        self._incident_id = incident_id
        self._kind = kind
        self._event_type = _require_text(event_type, "event_type")
        self._reason = _require_text(reason, "reason")
        self._severity = _require_text(severity, "severity")
        self._service = _require_text(service, "service")
        self._link = _require_text(link, "link")
        self._dedupe_key = _require_text(dedupe_key, "dedupe_key")
        self._rca_version = rca_version
        self._created_at = _require_aware(created_at, "created_at")

    @classmethod
    def rca_ready(
        cls,
        *,
        incident_id: UUID,
        severity: str,
        service: str,
        rca_version: int,
        created_at: datetime | None = None,
        notification_id: UUID | None = None,
    ) -> Notification:
        return cls(
            id=notification_id or uuid4(),
            incident_id=incident_id,
            kind=NotificationKind.RCA_READY,
            event_type="rca.completed.v1",
            reason="pending_review",
            severity=severity,
            service=service,
            link=f"/api/v1/incidents/{incident_id}/investigation",
            dedupe_key=f"rca_ready:{rca_version}",
            rca_version=rca_version,
            created_at=created_at or _utc_now(),
        )

    @classmethod
    def escalation(
        cls,
        *,
        incident_id: UUID,
        severity: str,
        service: str,
        reason: str,
        created_at: datetime | None = None,
        notification_id: UUID | None = None,
    ) -> Notification:
        cleaned = reason.strip()
        return cls(
            id=notification_id or uuid4(),
            incident_id=incident_id,
            kind=NotificationKind.ESCALATION,
            event_type="rca.escalated.v1",
            reason=cleaned,
            severity=severity,
            service=service,
            link=f"/api/v1/incidents/{incident_id}/investigation",
            dedupe_key=f"escalation:{cleaned}",
            rca_version=None,
            created_at=created_at or _utc_now(),
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def incident_id(self) -> UUID:
        return self._incident_id

    @property
    def kind(self) -> NotificationKind:
        return self._kind

    @property
    def event_type(self) -> str:
        return self._event_type

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def severity(self) -> str:
        return self._severity

    @property
    def service(self) -> str:
        return self._service

    @property
    def link(self) -> str:
        return self._link

    @property
    def dedupe_key(self) -> str:
        return self._dedupe_key

    @property
    def rca_version(self) -> int | None:
        return self._rca_version

    @property
    def created_at(self) -> datetime:
        return self._created_at
