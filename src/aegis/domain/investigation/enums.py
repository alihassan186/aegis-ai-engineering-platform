"""Investigation vocabulary (FR-022, FR-023, FR-025, FR-026).

Escalate reasons are the product language for *why* the commander stopped.
Step 4.9 exposes them on the progress API; 4.10 notifies on them.
Routing must not invent parallel strings.
"""

from enum import StrEnum


class EscalateReason(StrEnum):
    """First-class escalate outcomes — not exceptions."""

    MAX_HOPS = "max_hops"
    MAX_DURATION = "max_duration"
    LOW_CONFIDENCE = "low_confidence"
    AGENT_FAILURE = "agent_failure"
    # v0.5 first-hop policy for FR-083 dependency_failure (human owns vendor/outage).
    DEPENDENCY_FAILURE = "dependency_failure"
    RCA_REJECTED = "rca_rejected"


class InvestigationStepStatus(StrEnum):
    """FR-022 step states. Not a LangGraph debug dump."""

    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"


class InvestigationRunStatus(StrEnum):
    """Coarse investigation run status persisted for the progress API."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    PENDING_REVIEW = "pending_review"
    ESCALATED = "escalated"
