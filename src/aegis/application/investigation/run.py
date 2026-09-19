"""Invoke helpers. The worker calls these via ``InvestigationRunner``.

``thread_id`` equals ``incident_id`` in v0.5 so Step 4.9 can resume the same
thread. ``InMemorySaver`` is process-local: a worker restart loses pause
state. A Postgres checkpointer is the production follow-up — do not treat
memory as durable.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from aegis.application.investigation.collect import SpecialistPorts
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
    correlation_id: str = "",
    ports: SpecialistPorts | None = None,
) -> dict[str, Any]:
    """Run (or resume) one investigation thread.

    Pass ``resume`` after an interrupt (e.g. ``dependency_failure``).
    ``thread_id`` must be the same across pause and resume. When omitted,
    it is ``incident_id``.
    """
    saver = checkpointer or InMemorySaver()
    graph = compile_investigation_graph(checkpointer=saver, ports=ports)
    iid = (incident_id or "").strip()
    tid = (thread_id or iid or str(uuid4())).strip()
    config: RunnableConfig = {"configurable": {"thread_id": tid}}

    if resume is not None:
        result = graph.invoke(Command(resume=resume), config)
    else:
        payload: InvestigationState = {
            "incident_id": iid or f"INC-LEARN-{tid[:8]}",
            "service": service,
            "scenario": scenario,
            "hops": 0,
            "next_agent": "",
            "status": "",
            "human_decision": "",
            "evidence": [],
            "log": [],
            "failed_steps": [],
            "correlation_id": correlation_id,
        }
        result = graph.invoke(payload, config)

    result["_thread_id"] = tid
    result["_graph"] = graph
    return result
