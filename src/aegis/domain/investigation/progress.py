"""Investigation progress — persisted read model for FR-022 / FR-023.

The API reads this, not LangGraph state. Graph resume still needs a
durable checkpointer (InMemorySaver is process-local).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID, uuid4

from aegis.domain.investigation.enums import InvestigationRunStatus, InvestigationStepStatus
from aegis.shared.exceptions import ValidationError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(moment: datetime, field_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValidationError(f"{field_name} must be timezone-aware.")
    return moment


class InvestigationStep:
    def __init__(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        name: str,
        status: InvestigationStepStatus,
        detail: str,
        occurred_at: datetime,
    ) -> None:
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("step name must not be empty.")
        self._id = id
        self._incident_id = incident_id
        self._name = cleaned
        self._status = status
        self._detail = detail.strip()
        self._occurred_at = _require_aware(occurred_at, "occurred_at")

    @classmethod
    def create(
        cls,
        *,
        incident_id: UUID,
        name: str,
        status: InvestigationStepStatus,
        detail: str = "",
        occurred_at: datetime | None = None,
        step_id: UUID | None = None,
    ) -> InvestigationStep:
        return cls(
            id=step_id or uuid4(),
            incident_id=incident_id,
            name=name,
            status=status,
            detail=detail,
            occurred_at=occurred_at or _utc_now(),
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def incident_id(self) -> UUID:
        return self._incident_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> InvestigationStepStatus:
        return self._status

    @property
    def detail(self) -> str:
        return self._detail

    @property
    def occurred_at(self) -> datetime:
        return self._occurred_at


class InvestigationProgress:
    """One row per incident. Pause is a cooperative flag, not SIGKILL."""

    def __init__(
        self,
        *,
        incident_id: UUID,
        hops: int,
        status: InvestigationRunStatus,
        escalate_reason: str,
        paused: bool,
        steps: Sequence[InvestigationStep],
        updated_at: datetime,
    ) -> None:
        if incident_id is None:
            raise ValidationError("incident_id is required.")
        if hops < 0:
            raise ValidationError("hops must be >= 0.")
        self._incident_id = incident_id
        self._hops = hops
        self._status = status
        self._escalate_reason = escalate_reason.strip()
        self._paused = paused
        self._steps = tuple(steps)
        self._updated_at = _require_aware(updated_at, "updated_at")

    @classmethod
    def create(
        cls,
        *,
        incident_id: UUID,
        hops: int = 0,
        status: InvestigationRunStatus = InvestigationRunStatus.NOT_STARTED,
        escalate_reason: str = "",
        paused: bool = False,
        steps: Sequence[InvestigationStep] = (),
        updated_at: datetime | None = None,
    ) -> InvestigationProgress:
        return cls(
            incident_id=incident_id,
            hops=hops,
            status=status,
            escalate_reason=escalate_reason,
            paused=paused,
            steps=steps,
            updated_at=updated_at or _utc_now(),
        )

    @property
    def incident_id(self) -> UUID:
        return self._incident_id

    @property
    def hops(self) -> int:
        return self._hops

    @property
    def status(self) -> InvestigationRunStatus:
        return self._status

    @property
    def escalate_reason(self) -> str:
        return self._escalate_reason

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def steps(self) -> tuple[InvestigationStep, ...]:
        return self._steps

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    def with_pause(self, paused: bool) -> InvestigationProgress:
        status = InvestigationRunStatus.PAUSED if paused else (
            InvestigationRunStatus.RUNNING
            if self._status is InvestigationRunStatus.PAUSED
            else self._status
        )
        return InvestigationProgress(
            incident_id=self._incident_id,
            hops=self._hops,
            status=status,
            escalate_reason=self._escalate_reason,
            paused=paused,
            steps=self._steps,
            updated_at=_utc_now(),
        )

    def with_rejection(self) -> InvestigationProgress:
        return InvestigationProgress(
            incident_id=self._incident_id,
            hops=self._hops,
            status=InvestigationRunStatus.ESCALATED,
            escalate_reason="rca_rejected",
            paused=False,
            steps=self._steps,
            updated_at=_utc_now(),
        )
