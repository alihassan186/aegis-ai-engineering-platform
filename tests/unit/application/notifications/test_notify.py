"""Notify on RCA ready / escalate without SMTP (FR-027, FR-028)."""

from __future__ import annotations

import logging
from uuid import UUID

from aegis.application.investigation.consume_opened import ConsumeOpenedIncident
from aegis.application.notifications.notify import NotifyInvestigation, notify_best_effort
from aegis.application.rca.record_rca import RecordRca
from aegis.core.protocols import NotificationMessage
from aegis.domain.events.envelope import incident_opened_v1
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import Severity
from aegis.domain.investigation.progress import InvestigationProgress
from aegis.domain.notifications.entity import Notification
from aegis.domain.rca.entity import RcaCitation, RcaReport
from aegis.domain.rca.enums import RcaFindingStatus
from aegis.infrastructure.notifications.log_notifier import LogNotifier
from tests.unit.application.incidents.fakes import FakeIncidentRepository, FakeProcessedEventStore


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.items: list[Notification] = []

    async def record_once(self, notification: Notification) -> bool:
        key = (notification.incident_id, notification.dedupe_key)
        if any((item.incident_id, item.dedupe_key) == key for item in self.items):
            return False
        self.items.append(notification)
        return True

    async def list_by_incident(self, incident_id: UUID) -> list[Notification]:
        return [item for item in self.items if item.incident_id == incident_id]


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[NotificationMessage] = []

    def notify(self, message: NotificationMessage) -> None:
        self.messages.append(message)


class _ExplodingNotifier:
    def notify(self, message: NotificationMessage) -> None:
        raise RuntimeError("slack unavailable")


class _RecordingRunner:
    def start(
        self,
        *,
        incident_id: str,
        service: str,
        scenario: str,
        correlation_id: str,
    ) -> None:
        return None


def _incident() -> Incident:
    return Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )


def _report(incident: Incident, *, version: int = 1) -> RcaReport:
    return RcaReport.create(
        incident_id=incident.id,
        summary="latency on checkout",
        root_cause="saturated workers",
        contributing_factors=["recent deploy"],
        confidence=0.84,
        finding_status=RcaFindingStatus.HYPOTHESIS,
        citations=[
            RcaCitation(evidence_id=incident.id, source="simulator", relevance="p99"),
        ],
        recommended_actions=["watch p99"],
        model_id="fake-llm",
        version=version,
    )


def _use_case() -> tuple[Incident, NotifyInvestigation, FakeNotifier, FakeNotificationRepository]:
    incident = _incident()
    repo = FakeNotificationRepository()
    notifier = FakeNotifier()
    return incident, NotifyInvestigation(repo, notifier), notifier, repo


async def test_rca_ready_notifies_once_per_version() -> None:
    incident, notify, notifier, repo = _use_case()
    report = _report(incident)

    first = await notify.rca_ready(incident, report)
    second = await notify.rca_ready(incident, report)

    assert first is True
    assert second is False
    assert len(notifier.messages) == 1
    assert len(repo.items) == 1
    message = notifier.messages[0]
    assert message.kind == "rca_ready"
    assert message.event_type == "rca.completed.v1"
    assert message.reason == "pending_review"
    assert message.rca_version == 1
    assert message.incident_id == str(incident.id)
    assert message.service == "payments-api"
    assert message.severity == "high"
    assert str(incident.id) in message.link


async def test_second_version_notifies_again() -> None:
    incident, notify, notifier, _repo = _use_case()
    await notify.rca_ready(incident, _report(incident, version=1))
    again = await notify.rca_ready(incident, _report(incident, version=2))
    assert again is True
    assert [item.rca_version for item in notifier.messages] == [1, 2]


async def test_escalation_includes_max_hops_and_low_confidence() -> None:
    incident, notify, notifier, repo = _use_case()

    assert await notify.escalated(incident, "max_hops") is True
    assert await notify.escalated(incident, "low_confidence") is True
    assert await notify.escalated(incident, "max_hops") is False

    reasons = [item.reason for item in notifier.messages]
    assert reasons == ["max_hops", "low_confidence"]
    assert all(item.event_type == "rca.escalated.v1" for item in notifier.messages)
    assert all(item.kind == "escalation" for item in notifier.messages)
    assert len(repo.items) == 2


async def test_payload_has_no_secrets_or_evidence_dump() -> None:
    incident, notify, notifier, _repo = _use_case()
    await notify.rca_ready(incident, _report(incident))
    dumped = " ".join(
        f"{message.incident_id} {message.kind} {message.event_type} "
        f"{message.severity} {message.service} {message.reason} {message.link}"
        for message in notifier.messages
    )
    assert "AKIA" not in dumped
    assert "xoxb-" not in dumped
    assert "Bearer " not in dumped
    assert "@" not in dumped
    assert "saturated workers" not in dumped
    assert "webhook" not in dumped.lower()


async def test_notifier_failure_does_not_raise_into_rca_path() -> None:
    incident = _incident()
    repo = FakeNotificationRepository()
    notify = NotifyInvestigation(repo, _ExplodingNotifier())
    await notify_best_effort(notify, incident=incident, report=_report(incident))
    assert len(repo.items) == 1


async def test_consume_rca_persist_notifies_once() -> None:
    incidents = FakeIncidentRepository()
    store = FakeProcessedEventStore()
    incident = _incident()
    await incidents.create(incident)
    report = _report(incident)
    stored: list[RcaReport] = []
    repo = FakeNotificationRepository()
    notifier = FakeNotifier()

    class _RcaRepo:
        async def add(self, item: RcaReport) -> RcaReport:
            stored.append(item)
            return item

        async def list_by_incident(self, incident_id: UUID) -> list[RcaReport]:
            return [item for item in stored if item.incident_id == incident_id]

    class _DrainingRunner(_RecordingRunner):
        def drain_recorded_rca(self) -> list[RcaReport]:
            return [report]

        def drain_recorded_progress(self) -> InvestigationProgress:
            return InvestigationProgress.create(incident_id=incident.id)

    consume = ConsumeOpenedIncident(
        incidents,
        store,
        runner=_DrainingRunner(),
        record_rca=RecordRca(_RcaRepo()),
        notify=NotifyInvestigation(repo, notifier),
    )
    event = incident_opened_v1(incident_id=str(incident.id), correlation_id="corr-notify")
    await consume.execute(event)
    await consume.execute(event)

    assert [item.id for item in stored] == [report.id]
    assert len(notifier.messages) == 1
    assert notifier.messages[0].event_type == "rca.completed.v1"


def test_log_notifier_captures_rca_ready_without_smtp(caplog: logging.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="aegis.notifications")
    LogNotifier().notify(
        NotificationMessage(
            incident_id="11111111-1111-1111-1111-111111111111",
            kind="rca_ready",
            event_type="rca.completed.v1",
            severity="high",
            service="payments-api",
            reason="pending_review",
            link="/api/v1/incidents/11111111-1111-1111-1111-111111111111/investigation",
            rca_version=1,
        )
    )
    assert "RCA ready for INC-" in caplog.text
    assert "smtplib" not in caplog.text
