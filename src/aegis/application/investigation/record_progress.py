"""Persist investigation progress after a graph run. No LangGraph here."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from aegis.core.protocols import InvestigationProgressRepository
from aegis.domain.investigation.enums import InvestigationRunStatus, InvestigationStepStatus
from aegis.domain.investigation.progress import InvestigationProgress, InvestigationStep

_KNOWN_STEPS = (
    "intake",
    "commander",
    "observability",
    "knowledge",
    "code",
    "synthesize",
)


class RecordInvestigationProgress:
    def __init__(self, repository: InvestigationProgressRepository) -> None:
        self._repository = repository

    async def persist(self, progress: InvestigationProgress) -> InvestigationProgress:
        return await self._repository.save(progress)


def progress_from_graph_result(
    incident_id: UUID,
    result: Mapping[str, Any],
) -> InvestigationProgress:
    hops = int(result.get("hops") or 0)
    raw_status = str(result.get("status") or "running")
    try:
        status = InvestigationRunStatus(raw_status)
    except ValueError:
        status = InvestigationRunStatus.RUNNING
    return InvestigationProgress.create(
        incident_id=incident_id,
        hops=hops,
        status=status,
        escalate_reason=str(result.get("escalate_reason") or ""),
        paused=False,
        steps=steps_from_graph_result(incident_id, result),
    )


def steps_from_graph_result(
    incident_id: UUID,
    result: Mapping[str, Any],
) -> list[InvestigationStep]:
    failed = {str(item).strip().lower() for item in result.get("failed_steps") or []}
    logs: Sequence[object] = result.get("log") or []
    now = datetime.now(timezone.utc)
    seen: dict[str, InvestigationStep] = {}
    for raw in logs:
        line = str(raw)
        name = line.split(" ", 1)[0].strip().lower()
        if name not in _KNOWN_STEPS:
            continue
        status = (
            InvestigationStepStatus.FAILED
            if name in failed
            else InvestigationStepStatus.COMPLETED
        )
        seen[name] = InvestigationStep.create(
            incident_id=incident_id,
            name=name,
            status=status,
            detail=line[:200],
            occurred_at=now,
        )
    for name in failed:
        if name in seen or name not in _KNOWN_STEPS:
            continue
        seen[name] = InvestigationStep.create(
            incident_id=incident_id,
            name=name,
            status=InvestigationStepStatus.FAILED,
            detail=f"{name} failed",
            occurred_at=now,
        )
    order = {name: index for index, name in enumerate(_KNOWN_STEPS)}
    return sorted(seen.values(), key=lambda step: order.get(step.name, 99))
