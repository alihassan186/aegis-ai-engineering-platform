"""
This module defines and compiles the investigation workflow as a graph of states and transitions, 
using the LangGraph framework. The graph represents the main automation flow for carrying out 
an investigation in the Aegis system. The code here specifies both the nodes (which are implemented 
as functions) and how they are connected, controlling which steps happen in what order and under 
what conditions.

Key components and concepts:

- StateGraph: The primary abstraction for building a workflow or state machine. States (nodes) 
  correspond to named functions that act on the InvestigationState.

- START and END: Special nodes that represent the beginning and end of the graph execution.

- Nodes as Functions: Each investigation phase is a function — such as 'intake', 'commander', 
  specialist tasks ('observability', 'knowledge', 'code'), 'synthesize', and 'escalate'.

- Static vs Conditional Edges: 
    - Static edges directly link nodes and indicate unconditional transitions (e.g., from 'intake' to 'commander').
    - Conditional edges allow routing logic (for example, after 'commander', choosing which specialist(s) to call next), 
      implemented via `add_conditional_edges` and routed by the `route_after_commander` function.

- Parallel "Send" Fan-Out: The architecture supports running multiple specialists in parallel 
  (fan-out) after the commander node, allowing the investigation to collect evidence or perform 
  analysis from several domains concurrently.

- InMemorySaver Checkpointer: An in-memory checkpoint system is used (InMemorySaver) to allow 
  interruptions and resumptions during investigation, mainly for testing. Note: This does not 
  persist across process restarts — for real durability, a database-backed checkpointer 
  (such as Postgres) would be needed.

- Bounded Cycles: Information gathered by specialists can send control back to the commander, 
  which may result in another deliberation or round of specialist calls, ultimately bounded 
  by a MAX_HOPS limit to avoid infinite loops.

- Workflow Steps:
    - Step 4.4: The commander node determines the next action via a planning policy.
    - Step 4.5: Specialist nodes collect relevant information, each through a "port", which 
      might wrap different implementation sources (a simulator, code analysis function, etc).
    - Step 4.8: The synthesize node uses an LLM (Large Language Model) through the LlmClient interface
      — typically a 'FakeLlm' in the test harness — to produce a final summary or conclusion.

- This module's graph logic is decoupled from real infrastructure (like persistent checkpoints) 
  to facilitate lightweight, testable workflows. The workflow and graph design can be tested 
  with in-memory state and fake models.

Refer to test cases to observe sample executions and coverage of edge cases, routing, and cycles.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from aegis.application.investigation.collect import SpecialistPorts
from aegis.application.investigation.nodes import (
    bind_specialists,
    commander,
    escalate,
    intake,
)
from aegis.application.investigation.routing import route_after_commander
from aegis.application.investigation.state import InvestigationState


def build_investigation_graph(ports: SpecialistPorts | None = None) -> StateGraph:
    resolved = ports or SpecialistPorts.memory()
    specialists = bind_specialists(resolved)
    graph = StateGraph(InvestigationState)
    graph.add_node("intake", intake)
    graph.add_node("commander", commander)
    graph.add_node("observability", specialists["observability"])
    graph.add_node("knowledge", specialists["knowledge"])
    graph.add_node("code", specialists["code"])
    graph.add_node("synthesize", specialists["synthesize"])
    graph.add_node("escalate", escalate)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "commander")
    graph.add_conditional_edges("commander", route_after_commander)
    graph.add_edge("observability", "commander")
    graph.add_edge("knowledge", "commander")
    graph.add_edge("code", "commander")
    graph.add_edge("synthesize", END)
    graph.add_edge("escalate", END)
    return graph


def compile_investigation_graph(
    checkpointer: InMemorySaver | None = None,
    ports: SpecialistPorts | None = None,
) -> CompiledStateGraph:
    saver = checkpointer or InMemorySaver()
    return build_investigation_graph(ports).compile(checkpointer=saver)


def draw_investigation_mermaid() -> str:
    """ASCII-friendly mermaid of the compiled topology (no LLM)."""
    return compile_investigation_graph().get_graph().draw_mermaid()
