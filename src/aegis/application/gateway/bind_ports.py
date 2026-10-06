"""Compose a gateway from 4.5 ports via the tool registry (Step 5.4).

Identity is bound per node in ``bind_specialists`` (Step 5.3), not here.
"""

from __future__ import annotations

from aegis.application.audit.append_audit import AppendAudit
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.registry import runners_for_ports
from aegis.application.investigation.collect import SpecialistPorts


def invoke_tool_for_ports(
    ports: SpecialistPorts,
    *,
    audit: AppendAudit | None = None,
) -> InvokeTool:
    """One gateway whose runners are named registry tools over bound ports."""
    return InvokeTool(
        tools=runners_for_ports(
            observability=ports.observability,
            code_search=ports.code_search,
            retrieve=ports.retrieve,
        ),
        audit=audit,
    )
