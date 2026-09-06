"""Compile the investigation ``StateGraph``.

Concepts wired here (study this file with the tests):

* ``StateGraph`` + ``START`` / ``END``
* Nodes as functions
* Static edges vs ``add_conditional_edges``
* ``Send`` fan-out (parallel specialists)
* ``InMemorySaver`` checkpointer — required for ``interrupt`` and resume
* Cycles (specialist → commander) bounded by ``MAX_HOPS``

This is **not** Step 4.3 complete: no SQS worker, no Claude, no retrieve.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from aegis.application.investigation.nodes import (
    code_agent,
    commander,
    escalate,
    intake,
    knowledge,
    observability,
    synthesize,
)
from aegis.application.investigation.routing import route_after_commander
from aegis.application.investigation.state import InvestigationState


def build_investigation_graph() -> StateGraph:
    graph = StateGraph(InvestigationState)
    graph.add_node("intake", intake)
    graph.add_node("commander", commander)
    graph.add_node("observability", observability)
    graph.add_node("knowledge", knowledge)
    graph.add_node("code", code_agent)
    graph.add_node("synthesize", synthesize)
    graph.add_node("escalate", escalate)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "commander")
    graph.add_conditional_edges("commander", route_after_commander)
    # Specialists return to the commander (a cycle). Fan-out uses the same edges.
    graph.add_edge("observability", "commander")
    graph.add_edge("knowledge", "commander")
    graph.add_edge("code", "commander")
    graph.add_edge("synthesize", END)
    graph.add_edge("escalate", END)
    return graph


def compile_investigation_graph(
    checkpointer: InMemorySaver | None = None,
) -> CompiledStateGraph:
    saver = checkpointer or InMemorySaver()
    return build_investigation_graph().compile(checkpointer=saver)


def draw_investigation_mermaid() -> str:
    """ASCII-friendly mermaid of the compiled topology (no LLM)."""
    return compile_investigation_graph().get_graph().draw_mermaid()
