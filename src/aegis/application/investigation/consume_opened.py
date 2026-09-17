"""Consume ``incident.opened.v1``: idempotent ``open`` → ``investigating`` (FR-020).

No boto3. LangGraph is reached only through ``InvestigationRunner`` after a
first-time transition. The worker deletes SQS only after this use case
returns and the session commits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from aegis.core.protocols import IncidentRepository, InvestigationRunner, ProcessedEventStore
from aegis.domain.events.envelope import INCIDENT_OPENED_V1, DomainEvent
from aegis.domain.incidents.enums import IncidentState
from aegis.domain.incidents.fingerprint import scenario_from_fingerprint
from aegis.shared.exceptions import NotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConsumeOpenedResult:
    incident_id: UUID
    state: IncidentState | None
    transitioned: bool
    already_processed: bool


class ConsumeOpenedIncident:
    def __init__(
        self,
        repository: IncidentRepository,
        processed_events: ProcessedEventStore,
        *,
        runner: InvestigationRunner | None = None,
    ) -> None:
        self._repository = repository
        self._processed_events = processed_events
        self._runner = runner

    async def execute(self, event: DomainEvent) -> ConsumeOpenedResult:
        extra = {
            "correlation_id": event.correlation_id,
            "incident_id": event.incident_id,
            "event_id": event.event_id,
            "event_type": event.event_type,
        }
        if event.event_type != INCIDENT_OPENED_V1:
            logger.error("unknown event_type; leave message for DLQ", extra=extra)
            raise ValueError(f"Unsupported event_type '{event.event_type}'.")

        try:
            incident_id = UUID(event.incident_id)
        except ValueError as exc:
            logger.error("poison incident_id; leave message for DLQ", extra=extra)
            raise ValueError("incident_id is not a UUID.") from exc

        claimed = await self._processed_events.record_once(
            incident_id=incident_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            event_id=event.event_id,
            correlation_id=event.correlation_id,
        )
        if not claimed:
            logger.info("duplicate incident.opened.v1; no-op ack", extra=extra)
            return ConsumeOpenedResult(
                incident_id=incident_id,
                state=None,
                transitioned=False,
                already_processed=True,
            )

        incident = await self._repository.get_by_id(incident_id)
        if incident is None:
            logger.error("incident missing; leave message for retry", extra=extra)
            raise NotFoundError(f"Incident '{incident_id}' was not found.")

        transitioned = incident.start_investigation()
        if transitioned:
            await self._repository.save(incident)
            logger.info("incident open → investigating", extra=extra)
            if self._runner is not None:
                self._runner.start(
                    incident_id=str(incident.id),
                    service=incident.affected_service,
                    scenario=scenario_from_fingerprint(incident.fingerprint),
                    correlation_id=event.correlation_id,
                )
        else:
            logger.info(
                "incident already %s; no-op ack",
                incident.state.value,
                extra=extra,
            )

        return ConsumeOpenedResult(
            incident_id=incident_id,
            state=incident.state,
            transitioned=transitioned,
            already_processed=False,
        )
