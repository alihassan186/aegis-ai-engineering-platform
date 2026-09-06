"""LangGraph primitives against the AEGIS investigation skeleton."""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from aegis.application.investigation.graph import (
    compile_investigation_graph,
    draw_investigation_mermaid,
)
from aegis.application.investigation.run import invoke_investigation


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
    names = [
        next(iter(chunk))
        for chunk in graph.stream(_payload("latency_spike"), config)
    ]
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
