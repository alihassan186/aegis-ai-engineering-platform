"""Post-incident report assembly (FR-101). No OpenSearch write."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import UUID

import pytest

from aegis.application.reports.build_post_incident import BuildPostIncidentReport
from aegis.domain.evidence import Evidence, EvidenceKind, EvidenceSource
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.domain.investigation.enums import InvestigationStepStatus
from aegis.domain.investigation.progress import InvestigationProgress, InvestigationStep
from aegis.domain.notifications.entity import Notification
from aegis.domain.rca.entity import RcaCitation, RcaReport
from aegis.domain.rca.enums import RcaFindingStatus, RcaReviewStatus
from aegis.shared.exceptions import NotFoundError, ValidationError
from tests.unit.application.evidence.fakes import FakeEvidenceRepository
from tests.unit.application.incidents.fakes import FakeIncidentRepository
from tests.unit.application.investigation.test_transition_rca import (
    FakeProgressRepository,
    FakeRcaRepository,
)
from tests.unit.application.notifications.test_notify import FakeNotificationRepository

_DUMMY_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"


class _ExplodingKnowledge:
    """Must never be constructed by the report builder."""


def _identified() -> Incident:
    incident = Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )
    incident.transition_to(IncidentState.INVESTIGATING)
    incident.transition_to(IncidentState.IDENTIFIED)
    return incident


async def test_builder_includes_evidence_and_accepted_root_cause() -> None:
    incident = _identified()
    incidents = FakeIncidentRepository()
    await incidents.create(incident)
    evidence_repo = FakeEvidenceRepository()
    evidence = Evidence.create(
        incident_id=incident.id,
        source=EvidenceSource.SIMULATOR,
        kind=EvidenceKind.LOG,
        content_ref="simulator:payments-api:log",
        summary=f"p99 timeout token {_DUMMY_AWS_KEY}",
    )
    await evidence_repo.add(evidence)
    rca = FakeRcaRepository()
    accepted = RcaReport.create(
        incident_id=incident.id,
        summary="workers saturated after deploy",
        root_cause="thread pool exhaustion",
        contributing_factors=["2.8.1"],
        confidence=0.9,
        finding_status=RcaFindingStatus.HYPOTHESIS,
        citations=[RcaCitation(evidence_id=evidence.id, source="simulator", relevance="p99")],
        recommended_actions=["raise worker count", "watch p99"],
        model_id="fake-llm",
        review_status=RcaReviewStatus.ACCEPTED,
    )
    rca.items.append(accepted)
    progress = FakeProgressRepository()
    progress.items[incident.id] = InvestigationProgress.create(
        incident_id=incident.id,
        hops=2,
        steps=[
            InvestigationStep.create(
                incident_id=incident.id,
                name="commander",
                status=InvestigationStepStatus.COMPLETED,
                detail="plan",
            )
        ],
    )
    notes = FakeNotificationRepository()
    await notes.record_once(
        Notification.rca_ready(
            incident_id=incident.id,
            severity=incident.severity.value,
            service=incident.affected_service,
            rca_version=1,
        )
    )

    report = await BuildPostIncidentReport(
        incidents, evidence_repo, rca, progress, notes
    ).execute(incident.id)

    assert [item.id for item in report.evidence] == [evidence.id]
    assert report.accepted_root_cause == "thread pool exhaustion"
    assert report.recommended_actions == ("raise worker count", "watch p99")
    assert any(item.kind == "state" for item in report.timeline)
    assert any("commander" in item.detail for item in report.timeline)
    assert report.notifications[0].kind == "rca_ready"
    assert _DUMMY_AWS_KEY not in report.evidence[0].summary
    assert _DUMMY_AWS_KEY not in report.markdown
    assert "[REDACTED:aws_access_key]" in report.evidence[0].summary
    assert "thread pool exhaustion" in report.markdown
    assert str(evidence.id) in report.markdown
    assert "not indexed" in report.markdown


async def test_investigating_incident_is_not_reportable() -> None:
    incident = Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )
    incident.transition_to(IncidentState.INVESTIGATING)
    incidents = FakeIncidentRepository()
    await incidents.create(incident)
    builder = BuildPostIncidentReport(
        incidents,
        FakeEvidenceRepository(),
        FakeRcaRepository(),
        FakeProgressRepository(),
        FakeNotificationRepository(),
    )
    with pytest.raises(ValidationError, match="identified or closed"):
        await builder.execute(incident.id)


async def test_missing_incident_is_not_found() -> None:
    builder = BuildPostIncidentReport(
        FakeIncidentRepository(),
        FakeEvidenceRepository(),
        FakeRcaRepository(),
        FakeProgressRepository(),
        FakeNotificationRepository(),
    )
    with pytest.raises(NotFoundError):
        await builder.execute(UUID("11111111-1111-1111-1111-111111111111"))


def test_report_module_does_not_import_opensearch() -> None:
    path = Path("src/aegis/application/reports/build_post_incident.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    forbidden = (
        "opensearchpy",
        "opensearch",
        "aegis.infrastructure.search",
        "aegis.infrastructure.opensearch",
        "aegis.rag",
    )
    leaked = [
        name
        for name in names
        for item in forbidden
        if name == item or name.startswith(f"{item}.")
    ]
    assert leaked == []
    assert _ExplodingKnowledge is not None
