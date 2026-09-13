"""LocalStack + Postgres: publish → consume → investigating (FR-020)."""

from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.application.investigation.consume_opened import ConsumeOpenedIncident
from aegis.config.settings import Settings
from aegis.domain.events.envelope import INCIDENT_OPENED_V1, incident_opened_v1
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.infrastructure.messaging.provision import ensure_investigation_topology
from aegis.infrastructure.messaging.publisher import EventBridgePublisher, build_event_publisher
from aegis.infrastructure.messaging.sqs import (
    delete_message,
    domain_event_from_sqs_body,
    receive_one,
)
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository
from aegis.infrastructure.repositories.processed_event_store import SqlAlchemyProcessedEventStore


@pytest.fixture
def messaging_settings() -> Settings:
    endpoint = os.getenv("AEGIS_AWS_ENDPOINT", "").strip().rstrip("/")
    if not endpoint:
        pytest.skip("AEGIS_AWS_ENDPOINT is unset; LocalStack is optional for this suite.")
    return Settings(
        aws_endpoint=endpoint,
        aws_region=os.getenv("AEGIS_AWS_REGION", "").strip() or "eu-west-1",
        event_bus_name="aegis-events",
        investigation_queue_name="investigation-workflow",
    )


async def _consume(session: AsyncSession, event: object) -> None:
    await ConsumeOpenedIncident(
        SqlAlchemyIncidentRepository(session),
        SqlAlchemyProcessedEventStore(session),
    ).execute(event)  # type: ignore[arg-type]


@pytest.mark.integration
async def test_localstack_event_marks_incident_investigating(
    db_session: AsyncSession,
    messaging_settings: Settings,
) -> None:
    topology = ensure_investigation_topology(messaging_settings)
    assert topology.queue_name == "investigation-workflow"

    repo = SqlAlchemyIncidentRepository(db_session)
    incident = Incident.create(
        title="Worker 4.2",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )
    persisted = await repo.create(incident)
    await db_session.flush()

    publisher = build_event_publisher(messaging_settings)
    assert isinstance(publisher, EventBridgePublisher)
    event = incident_opened_v1(
        incident_id=str(persisted.id),
        correlation_id="int-4-2",
        event_id="evt-int-4-2",
    )
    publisher.publish(event)

    message = receive_one(messaging_settings, wait_seconds=20)
    assert message is not None
    parsed = domain_event_from_sqs_body(message["Body"])
    assert parsed.event_type == INCIDENT_OPENED_V1
    assert parsed.incident_id == str(persisted.id)

    await _consume(db_session, parsed)
    await db_session.flush()
    delete_message(messaging_settings, message["ReceiptHandle"])

    loaded = await repo.get_by_id(UUID(str(persisted.id)))
    assert loaded is not None
    assert loaded.state is IncidentState.INVESTIGATING

    again = await ConsumeOpenedIncident(
        repo,
        SqlAlchemyProcessedEventStore(db_session),
    ).execute(parsed)
    assert again.already_processed is True
    reloaded = await repo.get_by_id(persisted.id)
    assert reloaded is not None
    assert reloaded.state is IncidentState.INVESTIGATING
    assert len(reloaded.state_history) == 1
