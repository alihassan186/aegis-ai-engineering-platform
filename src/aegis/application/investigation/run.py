"""Invoke helpers. Call these from tests or ``python -m aegis.application.investigation``."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from aegis.application.investigation.graph import compile_investigation_graph
from aegis.application.investigation.state import InvestigationState


def invoke_investigation(
    *,
    service: str,
    scenario: str,
    incident_id: str | None = None,
    thread_id: str | None = None,
    checkpointer: InMemorySaver | None = None,
    resume: str | None = None,
) -> dict[str, Any]:
    """Run (or resume) one investigation thread.

    Pass ``resume`` after an interrupt (e.g. ``dependency_failure``).
    ``thread_id`` must be the same across pause and resume.
    """
    saver = checkpointer or InMemorySaver()
    graph = compile_investigation_graph(checkpointer=saver)
    tid = thread_id or str(uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": tid}}

    if resume is not None:
        result = graph.invoke(Command(resume=resume), config)
    else:
        payload: InvestigationState = {
            "incident_id": incident_id or f"INC-LEARN-{tid[:8]}",
            "service": service,
            "scenario": scenario,
            "hops": 0,
            "next_agent": "",
            "status": "",
            "human_decision": "",
            "evidence": [],
            "log": [],
        }
        result = graph.invoke(payload, config)

    result["_thread_id"] = tid
    result["_graph"] = graph
    return result
