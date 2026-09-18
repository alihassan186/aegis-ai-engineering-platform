"""Shared graph state.

LangGraph nodes do not return a new full object. They return a **partial
update**. Fields wrapped in ``Annotated[..., operator.add]`` use a
**reducer**: each update is appended, not replaced. That is how parallel
``Send`` nodes can both add evidence without clobbering each other.
"""

from __future__ import annotations

import operator
from datetime import timedelta
from typing import Annotated, NotRequired, TypedDict

# Commander stops looping after this many visits (cycle safety / RISK-010).
MAX_HOPS = 4

# After this many evidence lines the commander routes to synthesize (non-db).
ENOUGH_EVIDENCE = 1

# FR-026 wall-clock cap from ``started_at``. Hop cap still wins if both fire.
MAX_DURATION = timedelta(minutes=10)


class InvestigationState(TypedDict):
    """One investigation thread (one ``thread_id`` in the checkpointer)."""

    incident_id: str
    service: str
    scenario: str
    hops: int
    next_agent: str
    status: str
    human_decision: str
    evidence: Annotated[list[str], operator.add]
    log: Annotated[list[str], operator.add]
    # Filled only on the first node; NotRequired so invoke() can omit it.
    summary: NotRequired[str]
    correlation_id: NotRequired[str]
    # ISO-8601 UTC. Set once at intake; commander reads it for FR-026.
    started_at: NotRequired[str]
    # Domain ``EscalateReason`` value, or empty when not escalating.
    escalate_reason: NotRequired[str]
