"""Graph nodes — one function per role.

Each node receives the current ``InvestigationState`` and returns a
**dict of updates**. No FastAPI, no SQLAlchemy, no OpenSearch, no Bedrock.

``commander`` is a thin adapter over ``plan.next_action`` (Step 4.4).
Specialists (Step 4.5) collect through ports bound when the graph is compiled.
``escalate`` calls ``interrupt()``. The graph **pauses** until the caller
resumes with ``Command(resume=...)``. That is LangGraph's human-in-the-loop
primitive (preview of FR-034). A checkpointer is required.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from langgraph.types import interrupt

from aegis.application.evidence.record_evidence import EvidenceRecorder
from aegis.application.investigation.collect import (
    KnowledgeRetrieve,
    SpecialistPorts,
    collect_code,
    collect_knowledge,
    collect_observability,
)
from aegis.application.investigation.plan import next_action
from aegis.application.investigation.state import InvestigationState
from aegis.core.protocols import CodeSearch, ObservabilitySource

NodeFn = Callable[[InvestigationState], dict[str, object]]


def intake(state: InvestigationState) -> dict[str, object]:
    """Normalise the starting payload (START → intake)."""
    incident_id = state.get("incident_id") or "INC-LEARN"
    service = state.get("service") or "payment"
    scenario = state.get("scenario") or "latency_spike"
    started_at = state.get("started_at") or datetime.now(timezone.utc).isoformat()
    return {
        "incident_id": incident_id,
        "service": service,
        "scenario": scenario,
        "hops": state.get("hops") or 0,
        "next_agent": "",
        "status": "running",
        "human_decision": state.get("human_decision") or "",
        "started_at": started_at,
        "escalate_reason": state.get("escalate_reason") or "",
        "summary": f"{service}/{scenario}",
        "log": [
            f"intake {incident_id} {service}/{scenario}"
            + (f" corr={state['correlation_id']}" if state.get("correlation_id") else "")
        ],
    }


def commander(state: InvestigationState) -> dict[str, object]:
    """Read state, call the plan, write ``next_agent`` + hop increment."""
    hops = int(state.get("hops") or 0) + 1
    decision = next_action(
        scenario=state["scenario"],
        hops=hops,
        evidence=list(state.get("evidence") or []),
        started_at=state.get("started_at"),
        failed_steps=list(state.get("failed_steps") or []),
    )
    nxt = decision.next_agent.value
    reason = decision.escalate_reason.value if decision.escalate_reason else ""
    log = f"commander hop={hops} → {nxt}"
    if reason:
        log = f"{log} ({reason})"
    return {
        "hops": hops,
        "next_agent": nxt,
        "escalate_reason": reason,
        "log": [log],
    }


def observability_node(
    source: ObservabilitySource,
    recorder: EvidenceRecorder | None = None,
) -> NodeFn:
    def observability(state: InvestigationState) -> dict[str, object]:
        return collect_observability(state, source, recorder=recorder)

    return observability


def knowledge_node(
    retrieve: KnowledgeRetrieve | None,
    recorder: EvidenceRecorder | None = None,
) -> NodeFn:
    def knowledge(state: InvestigationState) -> dict[str, object]:
        return collect_knowledge(state, retrieve, recorder=recorder)

    return knowledge


def code_node(search: CodeSearch, recorder: EvidenceRecorder | None = None) -> NodeFn:
    def code_agent(state: InvestigationState) -> dict[str, object]:
        return collect_code(state, search, recorder=recorder)

    return code_agent


def bind_specialists(ports: SpecialistPorts) -> dict[str, NodeFn]:
    recorder = ports.recorder
    return {
        "observability": observability_node(ports.observability, recorder),
        "knowledge": knowledge_node(ports.retrieve, recorder),
        "code": code_node(ports.code_search, recorder),
    }


def synthesize(state: InvestigationState) -> dict[str, object]:
    """Stub RCA fold — Claude + schema is Step 4.8. No LLM here."""
    joined = "; ".join(_evidence_label(item) for item in state.get("evidence") or [])
    return {
        "status": "ready",
        "summary": f"draft from {len(state.get('evidence') or [])} evidence items: {joined}",
        "log": ["synthesize ready (no Claude in this skeleton)"],
    }


def escalate(state: InvestigationState) -> dict[str, object]:
    """Pause for a human. Resume with ``Command(resume='approve'|'reject')``."""
    reason = state.get("escalate_reason") or state.get("next_agent") or "escalate"
    decision = interrupt(
        {
            "type": "human_approval",
            "incident_id": state["incident_id"],
            "reason": reason,
        }
    )
    return {
        "human_decision": str(decision),
        "status": "escalated",
        "log": [f"human_decision={decision}"],
    }


def _evidence_label(item: object) -> str:
    if isinstance(item, dict):
        collector = item.get("collector") or item.get("kind") or "item"
        summary = item.get("summary") or item.get("text") or ""
        return f"{collector}:{str(summary)[:40]}"
    return str(item)
