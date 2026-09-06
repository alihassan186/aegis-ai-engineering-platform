"""Conditional edges and fan-out.

A **static edge** is always taken (``add_edge("a", "b")``).
A **conditional edge** is a function that returns the next node name.

``Send`` is a third form: run one or more nodes **in parallel**, each with
its own input payload. ``db_exhaustion`` fans out to observability +
knowledge in one super-step (reducers merge their evidence lists).
"""

from __future__ import annotations

from langgraph.types import Send

from aegis.application.investigation.state import InvestigationState


def route_after_commander(state: InvestigationState) -> str | list[Send]:
    nxt = state.get("next_agent") or "knowledge"
    if nxt == "fanout":
        return [
            Send("observability", state),
            Send("knowledge", state),
        ]
    return nxt
