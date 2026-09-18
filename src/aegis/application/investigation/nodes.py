"""Graph nodes — one function per role.

Each node receives the current ``InvestigationState`` and returns a
**dict of updates**. No FastAPI, no SQLAlchemy, no OpenSearch, no Bedrock.

``commander`` is a thin adapter over ``plan.next_action`` (Step 4.4).
``escalate`` calls ``interrupt()``. The graph **pauses** until the caller
resumes with ``Command(resume=...)``. That is LangGraph's human-in-the-loop
primitive (preview of FR-034). A checkpointer is required.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import interrupt

from aegis.application.investigation.plan import next_action
from aegis.application.investigation.state import InvestigationState


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
