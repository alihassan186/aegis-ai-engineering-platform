"""LangGraph investigation skeleton (learning + future Step 4.3).

This package teaches LangGraph against AEGIS vocabulary. It does **not**
replace Phase 3 RAG, call OpenSearch, or invoke Bedrock. The Knowledge
node is a stub until ``POST /api/v1/retrieve`` exists (Step 3.5).

The webhook path (HMAC → Postgres) is unchanged. Phase 4 will hang this
graph off the investigation worker (ADR-003), not off ``/emit``.
"""

from aegis.application.investigation.graph import (
    compile_investigation_graph,
    draw_investigation_mermaid,
)
from aegis.application.investigation.run import invoke_investigation

__all__ = [
    "compile_investigation_graph",
    "draw_investigation_mermaid",
    "invoke_investigation",
]
