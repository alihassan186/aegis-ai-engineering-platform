"""Shared graph state.

LangGraph nodes do not return a new full object. They return a **partial
update**. Fields wrapped in ``Annotated[..., operator.add]`` use a
**reducer**: each update is appended, not replaced. That is how parallel
``Send`` nodes can both add evidence without clobbering each other.

``evidence`` items are structured dicts (Step 4.5). Persist to Postgres is 4.6.
"""

from __future__ import annotations

import operator
from datetime import timedelta
from typing import Annotated, NotRequired, TypedDict

# MAX_HOPS determines the maximum number of steps (or "hops") the investigation commander can perform
# during an investigation. This is a safety feature to prevent the system from entering an infinite loop
# by enforcing a hard cap on the number of node transitions, as described in risk mitigation (see RISK-010).
# Each "hop" typically represents a decision, call to a specialist, or a jump to a new graph node.
MAX_HOPS = 4

# ENOUGH_EVIDENCE sets the minimum number of evidence items required before moving the investigation process
# towards synthesis (e.g., having the commander summarize or synthesize actions, rather than collecting more raw evidence).
# This ensures that the process converges efficiently and does not stall waiting for an unbounded amount of evidence.
# This also helps balance completeness of investigation with performance and resource usage.
ENOUGH_EVIDENCE = 1

# MAX_DURATION specifies the maximum wall-clock time allowed for an investigation thread, counted
# from the time recorded in 'started_at'. If this time cap is reached, the investigation is terminated regardless of hop count.
# The hop cap (MAX_HOPS) always takes precedence if both the hop and duration limits are hit simultaneously.
# This is designed to enforce fairness and avoid long-running, stuck, or zombie investigations (see FR-026).
MAX_DURATION = timedelta(minutes=10)

# The following caps are soft limits designed to keep responses tractable for both users and LLMs called by
# the system, such as Claude (until version 4.8). These affect summary outputs and how much information is passed to the LLMs:
# - OBS_MAX_ITEMS: Limits the number of observability signals (e.g., logs, traces, metrics) sampled per investigation step
#                  to ensure payloads are manageable and can be summarized by an LLM in a single operation.
# - KNOWLEDGE_MAX_CHUNKS: Restricts the number of knowledge/context chunks (such as code or documentation segments)
#                         retrieved and included for use by the investigation graph, preventing overload and lost focus.
# - EVIDENCE_TEXT_CAP: Puts a character cap on synthesized evidence string length, so that generated summaries
#                      remain within a sane range, helping integrity, readability, and LLM performance.
OBS_MAX_ITEMS = 20
KNOWLEDGE_MAX_CHUNKS = 4
EVIDENCE_TEXT_CAP = 800


class InvestigationState(TypedDict):
    """One investigation thread (one ``thread_id`` in the checkpointer)."""

    incident_id: str
    service: str
    scenario: str
    hops: int
    next_agent: str
    status: str
    human_decision: str
    evidence: Annotated[list[dict[str, object]], operator.add]
    log: Annotated[list[str], operator.add]
    failed_steps: Annotated[list[str], operator.add]
    # Filled only on the first node; NotRequired so invoke() can omit it.
    summary: NotRequired[str]
    correlation_id: NotRequired[str]
    # ISO-8601 UTC. Set once at intake; commander reads it for FR-026.
    started_at: NotRequired[str]
    # Domain ``EscalateReason`` value, or empty when not escalating.
    escalate_reason: NotRequired[str]
    title: NotRequired[str]
