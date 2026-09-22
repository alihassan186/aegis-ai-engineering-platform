"""RCA report — structured, cited, versioned (FR-030–035).

Incident stays the lifecycle aggregate. Humans accept before ``identified``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from aegis.domain.rca.enums import RcaFindingStatus, RcaReviewStatus, RcaVersionKind
from aegis.shared.exceptions import ValidationError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(moment: datetime, field_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValidationError(f"{field_name} must be timezone-aware.")
    return moment


# The leading underscore in a function name like `_require_text` is a Python naming convention
# indicating that the function is intended for *internal use* within the module or class—it is *private* by convention (although not enforced).
# This helps signal to other developers that this function is not part of the public API.

# There are other function naming conventions as well:
# - No underscore: e.g., `validate_text` (public, part of the API)
# - Single underscore (`_`): internal/private use by convention
# - Double leading underscore (`__`): triggers name mangling for class-internal functions (stronger privacy)
# - Dunder (double underscore both sides): e.g., `__init__` are special Python “magic” methods

def _require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field_name} must not be empty.")
    return cleaned


class RcaCitation:
    def __init__(self, *, evidence_id: UUID, source: str, relevance: str) -> None:
        if evidence_id is None:
            raise ValidationError("evidence_id is required.")
        self._evidence_id = evidence_id
        self._source = source.strip()
        self._relevance = relevance.strip()

    @property
    def evidence_id(self) -> UUID:
        return self._evidence_id

    @property
    def source(self) -> str:
        return self._source

    @property
    def relevance(self) -> str:
        return self._relevance

    def as_dict(self) -> dict[str, str]:
        return {
            "evidence_id": str(self._evidence_id),
            "source": self._source,
            "relevance": self._relevance,
        }


class RcaReport:
    """One RCA version. Amend in 4.9 inserts another row, not an edit in place."""

    def __init__(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        version: int,
        version_kind: RcaVersionKind,
        summary: str,
        root_cause: str,
        contributing_factors: Sequence[str],
        confidence: float,
        finding_status: RcaFindingStatus,
        review_status: RcaReviewStatus,
        citations: Sequence[RcaCitation],
        recommended_actions: Sequence[str],
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        created_at: datetime,
    ) -> None:
        if incident_id is None:
            raise ValidationError("incident_id is required.")
        if not 0.0 <= confidence <= 1.0:
            raise ValidationError("confidence must be between 0 and 1.")
        if version < 1:
            raise ValidationError("version must be >= 1.")
        if not citations:
            raise ValidationError("RCA requires at least one evidence citation.")
        self._id = id
        self._incident_id = incident_id
        self._version = version
        self._version_kind = version_kind
        self._summary = _require_text(summary, "summary")
        self._root_cause = _require_text(root_cause, "root_cause")
        self._contributing_factors = tuple(
            item.strip() for item in contributing_factors if item.strip()
        )
        self._confidence = confidence
        self._finding_status = finding_status
        self._review_status = review_status
        self._citations = tuple(citations)
        self._recommended_actions = tuple(
            item.strip() for item in recommended_actions if item.strip()
        )
        self._model_id = _require_text(model_id, "model_id")
        self._input_tokens = max(0, input_tokens)
        self._output_tokens = max(0, output_tokens)
        self._created_at = _require_aware(created_at, "created_at")

    @classmethod
    def create(
        cls,
        *,
        incident_id: UUID,
        summary: str,
        root_cause: str,
        contributing_factors: Sequence[str],
        confidence: float,
        finding_status: RcaFindingStatus,
        citations: Sequence[RcaCitation],
        recommended_actions: Sequence[str],
        model_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        version: int = 1,
        version_kind: RcaVersionKind = RcaVersionKind.ORIGINAL,
        review_status: RcaReviewStatus = RcaReviewStatus.PENDING_REVIEW,
        created_at: datetime | None = None,
        report_id: UUID | None = None,
    ) -> RcaReport:
        return cls(
            id=report_id or uuid4(),
            incident_id=incident_id,
            version=version,
            version_kind=version_kind,
            summary=summary,
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            confidence=confidence,
            finding_status=finding_status,
            review_status=review_status,
            citations=citations,
            recommended_actions=recommended_actions,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            created_at=created_at or _utc_now(),
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def incident_id(self) -> UUID:
        return self._incident_id

    @property
    def version(self) -> int:
        return self._version

    @property
    def version_kind(self) -> RcaVersionKind:
        return self._version_kind

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def root_cause(self) -> str:
        return self._root_cause

    @property
    def contributing_factors(self) -> tuple[str, ...]:
        return self._contributing_factors

    @property
    def confidence(self) -> float:
        return self._confidence

    @property
    def finding_status(self) -> RcaFindingStatus:
        return self._finding_status

    @property
    def review_status(self) -> RcaReviewStatus:
        return self._review_status

    @property
    def citations(self) -> tuple[RcaCitation, ...]:
        return self._citations

    @property
    def recommended_actions(self) -> tuple[str, ...]:
        return self._recommended_actions

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def input_tokens(self) -> int:
        return self._input_tokens

    @property
    def output_tokens(self) -> int:
        return self._output_tokens

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self._id),
            "incident_id": str(self._incident_id),
            "version": self._version,
            "version_kind": self._version_kind.value,
            "summary": self._summary,
            "root_cause": self._root_cause,
            "contributing_factors": list(self._contributing_factors),
            "confidence": self._confidence,
            "status": self._finding_status.value,
            "review_status": self._review_status.value,
            "evidence_citations": [item.as_dict() for item in self._citations],
            "recommended_actions": list(self._recommended_actions),
            "model_id": self._model_id,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "created_at": self._created_at.isoformat(),
        }


def citation_from_mapping(raw: Mapping[str, Any]) -> RcaCitation:
    return RcaCitation(
        evidence_id=UUID(str(raw["evidence_id"])),
        source=str(raw.get("source") or ""),
        relevance=str(raw.get("relevance") or ""),
    )
