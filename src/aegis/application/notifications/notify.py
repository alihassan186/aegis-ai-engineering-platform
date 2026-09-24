"""Notify on RCA ready or escalation (FR-027, FR-028).

Does not send email. Persist a row, then call ``Notifier``. A notifier
failure must not undo the RCA write — callers wrap ``execute`` in try/except.
"""

from __future__ import annotations

import logging
from uuid import UUID

from aegis.core.protocols import (
    NotificationMessage,
    NotificationRepository,
    Notifier,
)
from aegis.domain.incidents.entity import Incident
from aegis.domain.notifications.entity import Notification
from aegis.domain.rca.entity import RcaReport

logger = logging.getLogger(__name__)


class NotifyInvestigation:
    def __init__(self, repository: NotificationRepository, notifier: Notifier) -> None:
        self._repository = repository
        self._notifier = notifier

    async def rca_ready(self, incident: Incident, report: RcaReport) -> bool:
        row = Notification.rca_ready(
            incident_id=incident.id,
            severity=incident.severity.value,
            service=incident.affected_service,
            rca_version=report.version,
        )
        return await self._dispatch(row)

    async def escalated(self, incident: Incident, reason: str) -> bool:
        cleaned = reason.strip()
        if not cleaned:
            return False
        row = Notification.escalation(
            incident_id=incident.id,
            severity=incident.severity.value,
            service=incident.affected_service,
            reason=cleaned,
        )
        return await self._dispatch(row)

    async def list_for_incident(self, incident_id: UUID) -> list[Notification]:
        return await self._repository.list_by_incident(incident_id)

    async def _dispatch(self, row: Notification) -> bool:
        claimed = await self._repository.record_once(row)
        if not claimed:
            return False
        message = NotificationMessage(
            incident_id=str(row.incident_id),
            kind=row.kind.value,
            event_type=row.event_type,
            severity=row.severity,
            service=row.service,
            reason=row.reason,
            link=row.link,
            rca_version=row.rca_version,
        )
        self._notifier.notify(message)
        return True


async def notify_best_effort(
    notify: NotifyInvestigation | None,
    *,
    incident: Incident,
    report: RcaReport | None = None,
    escalate_reason: str = "",
) -> None:
    """Never raise into the RCA persist path."""
    if notify is None:
        return
    try:
        if report is not None:
            await notify.rca_ready(incident, report)
        if escalate_reason.strip():
            await notify.escalated(incident, escalate_reason)
    except Exception:
        logger.exception(
            "notification delivery failed; RCA persist is unchanged",
            extra={"incident_id": str(incident.id)},
        )
