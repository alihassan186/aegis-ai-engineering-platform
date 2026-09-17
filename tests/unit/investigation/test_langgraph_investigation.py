"""LangGraph primitives against the AEGIS investigation skeleton.

``InMemorySaver`` is required for interrupt/resume in these tests. It lives
in process memory and does **not** survive a worker restart. Production
needs a Postgres (or similar) checkpointer — Step 4.9 / later ops.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from aegis.application.investigation.graph import (
    compile_investigation_graph,
    draw_investigation_mermaid,
)
from aegis.application.investigation.run import invoke_investigation
from aegis.application.investigation.runner import LangGraphInvestigationRunner
from aegis.application.investigation.state import MAX_HOPS


def _payload(scenario: str, *, service: str = "payment") -> dict[str, object]:
    return {
        "incident_id": "INC-TEST",
        "service": service,
        "scenario": scenario,
        "hops": 0,
        "next_agent": "",
        "status": "",
        "human_decision": "",
        "evidence": [],
        "log": [],
    }


def test_latency_spike_reaches_synthesize_with_observability_evidence() -> None:
    result = invoke_investigation(service="payment", scenario="latency_spike")

    assert result["status"] == "ready"
    assert any(item.startswith("obs:payment:latency_spike") for item in result["evidence"])
    assert "synthesize ready" in " ".join(result["log"])


def test_bad_deployment_routes_through_code_node() -> None:
    result = invoke_investigation(service="user", scenario="bad_deployment")

    assert result["status"] == "ready"
    assert any(item.startswith("code:user:") for item in result["evidence"])


def test_db_exhaustion_fans_out_to_observability_and_knowledge() -> None:
    """``Send`` runs two specialists in one super-step; reducers merge evidence."""
    result = invoke_investigation(service="payment", scenario="db_exhaustion")

    kinds = {item.split(":")[0] for item in result["evidence"]}
    assert "obs" in kinds
    assert "kb-stub" in kinds
    assert result["status"] == "ready"


def test_dependency_failure_interrupts_then_resumes() -> None:
    saver = InMemorySaver()
    graph = compile_investigation_graph(checkpointer=saver)
    config: RunnableConfig = {"configurable": {"thread_id": "human-1"}}

    paused = graph.invoke(_payload("dependency_failure"), config)
    assert paused.get("__interrupt__")
    snapshot = graph.get_state(config)
    assert "escalate" in snapshot.next

    finished = graph.invoke(Command(resume="approve"), config)
    assert finished["human_decision"] == "approve"
    assert finished["status"] == "escalated"
    assert graph.get_state(config).next == ()


def test_stream_emits_node_updates() -> None:
    graph = compile_investigation_graph()
    config: RunnableConfig = {"configurable": {"thread_id": "stream-1"}}
    names = [next(iter(chunk)) for chunk in graph.stream(_payload("latency_spike"), config)]
    assert "intake" in names
    assert "commander" in names
    assert "observability" in names
    assert "synthesize" in names


def test_checkpointer_exposes_history() -> None:
    saver = InMemorySaver()
    graph = compile_investigation_graph(checkpointer=saver)
    config: RunnableConfig = {"configurable": {"thread_id": "history-1"}}
    graph.invoke(_payload("latency_spike"), config)

    history = list(graph.get_state_history(config))
    assert len(history) >= 2


def test_mermaid_contains_commander_and_specialists() -> None:
    diagram = draw_investigation_mermaid()
    assert "commander" in diagram
    assert "observability" in diagram
    assert "knowledge" in diagram


def test_hop_overflow_routes_to_escalate_never_spins() -> None:
    """RISK-010 / THR-014: hops > MAX_HOPS go to escalate, not another specialist."""
    saver = InMemorySaver()
    graph = compile_investigation_graph(checkpointer=saver)
    config: RunnableConfig = {"configurable": {"thread_id": "hop-cap"}}
    payload = _payload("latency_spike")
    payload["hops"] = MAX_HOPS

    paused = graph.invoke(payload, config)

    assert paused["next_agent"] == "escalate"
    assert paused["hops"] == MAX_HOPS + 1
    assert paused.get("__interrupt__")
    assert paused["hops"] <= MAX_HOPS + 1


def test_invoke_uses_incident_id_as_thread_id() -> None:
    incident_id = "11111111-1111-1111-1111-111111111111"
    result = invoke_investigation(
        service="payment",
        scenario="latency_spike",
        incident_id=incident_id,
        correlation_id="corr-1",
    )
    assert result["_thread_id"] == incident_id
    assert result["status"] == "ready"


def test_langgraph_runner_starts_compiled_graph() -> None:
    saver = InMemorySaver()
    runner = LangGraphInvestigationRunner(checkpointer=saver)
    runner.start(
        incident_id="22222222-2222-2222-2222-222222222222",
        service="payment",
        scenario="latency_spike",
        correlation_id="corr-2",
    )
    snapshot = compile_investigation_graph(checkpointer=saver).get_state(
        {"configurable": {"thread_id": "22222222-2222-2222-2222-222222222222"}}
    )
    assert snapshot.values.get("status") == "ready"
