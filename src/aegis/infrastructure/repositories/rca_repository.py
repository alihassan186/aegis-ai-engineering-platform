"""SQLAlchemy implementation of ``RcaRepository`` (ADR-001, ADR-002)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.domain.rca.entity import RcaCitation, RcaReport
from aegis.domain.rca.enums import RcaFindingStatus, RcaReviewStatus, RcaVersionKind
from aegis.infrastructure.database.models.rca import RcaReportModel


class SqlAlchemyRcaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: RcaReport) -> RcaReport:
        self._session.add(_to_orm(report))
        await self._session.flush()
        return report

    async def list_by_incident(self, incident_id: UUID) -> list[RcaReport]:
        stmt = (
            select(RcaReportModel)
            .where(RcaReportModel.incident_id == incident_id)
            .order_by(RcaReportModel.version.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]


def _to_orm(report: RcaReport) -> RcaReportModel:
    return RcaReportModel(
        id=report.id,
        incident_id=report.incident_id,
        version=report.version,
        version_kind=report.version_kind.value,
        summary=report.summary,
        root_cause=report.root_cause,
        contributing_factors=list(report.contributing_factors),
        confidence=report.confidence,
        finding_status=report.finding_status.value,
        review_status=report.review_status.value,
        evidence_citations=[item.as_dict() for item in report.citations],
        recommended_actions=list(report.recommended_actions),
        model_id=report.model_id,
        input_tokens=report.input_tokens,
        output_tokens=report.output_tokens,
        created_at=report.created_at,
    )


def _to_domain(row: RcaReportModel) -> RcaReport:
    citations = [
        RcaCitation(
            evidence_id=UUID(str(item["evidence_id"])),
            source=str(item.get("source") or ""),
            relevance=str(item.get("relevance") or ""),
        )
        for item in row.evidence_citations or []
        if isinstance(item, dict)
    ]
    return RcaReport(
        id=row.id,
        incident_id=row.incident_id,
        version=row.version,
        version_kind=RcaVersionKind(row.version_kind),
        summary=row.summary,
        root_cause=row.root_cause,
        contributing_factors=list(row.contributing_factors or []),
        confidence=row.confidence,
        finding_status=RcaFindingStatus(row.finding_status),
        review_status=RcaReviewStatus(row.review_status),
        citations=citations,
        recommended_actions=list(row.recommended_actions or []),
        model_id=row.model_id,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        created_at=row.created_at,
    )
