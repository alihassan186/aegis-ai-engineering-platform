"""Accept / reject / amend RCA without HTTP (FR-034, FR-035)."""

from __future__ import annotations

from uuid import UUID

from aegis.application.investigation.get_progress import GetInvestigationProgress
from aegis.application.investigation.transition_rca import AmendRcaCommand, TransitionRca
from aegis.domain.evidence import Evidence
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.domain.investigation.progress import InvestigationProgress
from aegis.domain.rca.entity import RcaCitation, RcaReport
from aegis.domain.rca.enums import RcaFindingStatus, RcaReviewStatus, RcaVersionKind
from tests.unit.application.incidents.fakes import FakeIncidentRepository


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.items: list[Evidence] = []

    async def add(self, evidence: Evidence) -> Evidence:
        self.items.append(evidence)
        return evidence

    async def list_by_incident(self, incident_id: UUID) -> list[Evidence]:
        return [item for item in self.items if item.incident_id == incident_id]


class FakeRcaRepository:
    def __init__(self) -> None:
        self.items: list[RcaReport] = []

    async def add(self, report: RcaReport) -> RcaReport:
        self.items.append(report)
        return report

    async def save(self, report: RcaReport) -> RcaReport:
        self.items = [report if item.id == report.id else item for item in self.items]
        return report

    async def list_by_incident(self, incident_id: UUID) -> list[RcaReport]:
        return [item for item in self.items if item.incident_id == incident_id]


class FakeProgressRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, InvestigationProgress] = {}

    async def get_by_incident(self, incident_id: UUID) -> InvestigationProgress | None:
        return self.items.get(incident_id)

    async def save(self, progress: InvestigationProgress) -> InvestigationProgress:
        self.items[progress.incident_id] = progress
        return progress


def _setup() -> tuple[Incident, TransitionRca, FakeRcaRepository]:
    incident = Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )
    incident.transition_to(IncidentState.INVESTIGATING)
    incidents = FakeIncidentRepository()
    incidents.items[incident.id] = incident
    evidence = FakeEvidenceRepository()
    rca = FakeRcaRepository()
    progress = FakeProgressRepository()
    citation = RcaCitation(
        evidence_id=incident.id,
        source="simulator",
        relevance="p99",
    )
    rca.items.append(
        RcaReport.create(
            incident_id=incident.id,
            summary="latency",
            root_cause="workers",
            contributing_factors=["deploy"],
            confidence=0.84,
            finding_status=RcaFindingStatus.HYPOTHESIS,
            citations=[citation],
            recommended_actions=["watch p99"],
            model_id="fake-llm",
        )
    )
    reader = GetInvestigationProgress(incidents, evidence, rca, progress)
    return incident, TransitionRca(incidents, rca, progress, reader), rca


async def test_accept_moves_incident_to_identified() -> None:
    incident, use_case, rca = _setup()
    dto = await use_case.accept(incident.id)
    assert dto.incident_state == "identified"
    assert rca.items[0].review_status is RcaReviewStatus.ACCEPTED
    again = await use_case.accept(incident.id)
    assert again.rca is not None
    assert again.rca.version == dto.rca.version  # type: ignore[union-attr]


async def test_reject_stays_investigating() -> None:
    incident, use_case, rca = _setup()
    dto = await use_case.reject(incident.id)
    assert dto.incident_state == "investigating"
    assert dto.escalate_reason == "rca_rejected"
    assert rca.items[0].review_status is RcaReviewStatus.REJECTED


async def test_amend_keeps_original_and_adds_version_two() -> None:
    incident, use_case, rca = _setup()
    dto = await use_case.amend(
        incident.id,
        AmendRcaCommand(
            summary="amended",
            root_cause="deploy plus workers",
            contributing_factors=["2.8.1"],
            confidence=0.9,
            status="hypothesis",
            recommended_actions=["rollback"],
        ),
    )
    assert [item.version for item in dto.rca_versions] == [1, 2]
    assert rca.items[0].version_kind is RcaVersionKind.ORIGINAL
    assert rca.items[1].version_kind is RcaVersionKind.AMENDED
    assert rca.items[1].review_status is RcaReviewStatus.PENDING_REVIEW
