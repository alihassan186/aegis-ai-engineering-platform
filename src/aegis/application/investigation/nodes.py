"""Graph nodes — one function per role.

Each node receives the current ``InvestigationState`` and returns a
**dict of updates**. No FastAPI, no SQLAlchemy, no OpenSearch, no Bedrock.

``escalate`` calls ``interrupt()``. The graph **pauses** until the caller
resumes with ``Command(resume=...)``. That is LangGraph's human-in-the-loop
primitive (preview of FR-034). A checkpointer is required.
"""

from __future__ import annotations

from langgraph.types import interrupt

from aegis.application.investigation.state import (
    ENOUGH_EVIDENCE,
    MAX_HOPS,
    InvestigationState,
)


def intake(state: InvestigationState) -> dict[str, object]:
    """Normalise the starting payload (START → intake)."""
    incident_id = state.get("incident_id") or "INC-LEARN"
    service = state.get("service") or "payment"
    scenario = state.get("scenario") or "latency_spike"
    return {
        "incident_id": incident_id,
        "service": service,
        "scenario": scenario,
        "hops": state.get("hops") or 0,
        "next_agent": "",
        "status": "running",
        "human_decision": state.get("human_decision") or "",
        "summary": f"{service}/{scenario}",
        "log": [f"intake {incident_id} {service}/{scenario}"],
    }


def commander(state: InvestigationState) -> dict[str, object]:
    """Decide the next node. Routing itself is the conditional edge."""
    hops = int(state.get("hops") or 0) + 1
    evidence = list(state.get("evidence") or [])
    scenario = state["scenario"]

    if hops > MAX_HOPS:
        nxt = "escalate"
    elif len(evidence) >= ENOUGH_EVIDENCE:
        nxt = "synthesize"
    elif scenario == "dependency_failure" and hops == 1:
        nxt = "escalate"
    elif scenario == "db_exhaustion" and hops == 1:
        nxt = "fanout"
    elif scenario == "bad_deployment":
        nxt = "code"
    elif scenario in {"latency_spike", "memory_leak", "queue_backlog"}:
        nxt = "observability"
    else:
        nxt = "knowledge"

    return {
        "hops": hops,
        "next_agent": nxt,
        "log": [f"commander hop={hops} → {nxt}"],
    }


def observability(state: InvestigationState) -> dict[str, object]:
    """Stub Observability Agent — no CloudWatch. Signals come in Phase 4.5."""
    line = f"obs:{state['service']}:{state['scenario']}"
    return {"evidence": [line], "log": [f"observability collected {line}"]}


def knowledge(state: InvestigationState) -> dict[str, object]:
    """Stub Knowledge Agent.

    After Step 3.5 this node should call the retrieve **use case**
    (not OpenSearch directly, not a LangChain retriever).
    """
    line = f"kb-stub:{state['service']}:{state['scenario']}"
    return {"evidence": [line], "log": [f"knowledge stub {line}"]}


def code_agent(state: InvestigationState) -> dict[str, object]:
    """Stub Code Agent — GitHub search is Phase 4 / 5."""
    line = f"code:{state['service']}:recent-deploy"
    return {"evidence": [line], "log": [f"code collected {line}"]}


def synthesize(state: InvestigationState) -> dict[str, object]:
    """Stub RCA fold — Claude + schema is Step 4.8. No LLM here."""
    joined = "; ".join(state.get("evidence") or [])
    return {
        "status": "ready",
        "summary": f"draft from {len(state.get('evidence') or [])} evidence items: {joined}",
        "log": ["synthesize ready (no Claude in this skeleton)"],
    }


def escalate(state: InvestigationState) -> dict[str, object]:
    """Pause for a human. Resume with ``Command(resume='approve'|'reject')``."""
    decision = interrupt(
        {
            "type": "human_approval",
            "incident_id": state["incident_id"],
            "reason": state.get("next_agent") or "escalate",
        }
    )
    return {
        "human_decision": str(decision),
        "status": "escalated",
        "log": [f"human_decision={decision}"],
    }
