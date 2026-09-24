"""Seed a fake investigation persist path for API tests."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from aegis.application.evidence.record_evidence import RecordEvidence
from aegis.application.investigation.record_progress import RecordInvestigationProgress
from aegis.application.rca.record_rca import RecordRca
from aegis.domain.evidence.enums import EvidenceKind, EvidenceSource
from aegis.domain.investigation.enums import InvestigationRunStatus, InvestigationStepStatus
from aegis.domain.investigation.progress import InvestigationProgress, InvestigationStep
from aegis.domain.rca.entity import RcaCitation, RcaReport
from aegis.domain.rca.enums import RcaFindingStatus
from aegis.infrastructure.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from aegis.infrastructure.repositories.investigation_repository import (
    SqlAlchemyInvestigationProgressRepository,
)
from aegis.infrastructure.repositories.rca_repository import SqlAlchemyRcaRepository


async def seed_fake_investigation(
    session: AsyncSession,
    incident_id: UUID | str,
    *,
    hops: int = 2,
) -> tuple[UUID, int]:
    """Persist evidence, steps, and a pending RCA as the worker would after 4.8."""
    incident_id = incident_id if isinstance(incident_id, UUID) else UUID(str(incident_id))
    evidence = await RecordEvidence(SqlAlchemyEvidenceRepository(session)).execute(
        incident_id=incident_id,
        source=EvidenceSource.SIMULATOR,
        kind=EvidenceKind.METRIC,
        content_ref="simulator:payment:metric",
        summary="p99 latency 1.8s on checkout",
    )
    report = RcaReport.create(
        incident_id=incident_id,
        summary="Checkout latency after a recent change.",
        root_cause="Saturated checkout workers.",
        contributing_factors=["Elevated error logs"],
        confidence=0.84,
        finding_status=RcaFindingStatus.HYPOTHESIS,
        citations=[
            RcaCitation(
                evidence_id=evidence.id,
                source="simulator",
                relevance="p99 on the payment path",
            )
        ],
        recommended_actions=["Restart checkout workers"],
        model_id="fake-llm",
    )
    await RecordRca(SqlAlchemyRcaRepository(session)).persist(report)
    progress = InvestigationProgress.create(
        incident_id=incident_id,
        hops=hops,
        status=InvestigationRunStatus.PENDING_REVIEW,
        steps=[
            InvestigationStep.create(
                incident_id=incident_id,
                name="intake",
                status=InvestigationStepStatus.COMPLETED,
                detail="intake completed",
            ),
            InvestigationStep.create(
                incident_id=incident_id,
                name="observability",
                status=InvestigationStepStatus.COMPLETED,
                detail="observability completed",
            ),
            InvestigationStep.create(
                incident_id=incident_id,
                name="synthesize",
                status=InvestigationStepStatus.COMPLETED,
                detail="synthesize pending_review",
            ),
        ],
    )
    await RecordInvestigationProgress(
        SqlAlchemyInvestigationProgressRepository(session)
    ).persist(progress)
    await session.flush()
    return evidence.id, report.version
