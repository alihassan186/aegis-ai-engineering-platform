"""Register 4.5 ports as named read tools. Nodes never import the clients.

Identity is bound per node in ``bind_specialists`` (Step 5.3), not here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aegis.application.gateway.invoke_tool import InvokeTool, ToolFn
from aegis.application.investigation.collect import (
    KnowledgeRetrieve,
    SpecialistPorts,
    _retrieve_runbooks_and_incidents,
)
from aegis.application.investigation.state import OBS_MAX_ITEMS
from aegis.core.protocols import CodeSearch, ObservabilitySource


def invoke_tool_for_ports(ports: SpecialistPorts) -> InvokeTool:
    """One gateway whose runners close over the bound ports."""
    tools: dict[str, ToolFn] = {
        "fetch_signals": _fetch_signals(ports.observability),
        "search_code": _search_code(ports.code_search),
        "list_deploys": _list_deploys(ports.code_search),
    }
    if ports.retrieve is not None:
        tools["retrieve_knowledge"] = _retrieve(ports.retrieve)
    return InvokeTool(tools=tools)


def _fetch_signals(source: ObservabilitySource) -> ToolFn:
    def run(params: Mapping[str, Any]) -> object:
        limit = int(params.get("limit") or OBS_MAX_ITEMS)
        return list(
            source.fetch_signals(
                service=str(params.get("service") or ""),
                scenario=str(params.get("scenario") or ""),
                limit=limit,
            )
        )

    return run


def _search_code(search: CodeSearch) -> ToolFn:
    def run(params: Mapping[str, Any]) -> object:
        return list(
            search.search(
                service=str(params.get("service") or ""),
                scenario=str(params.get("scenario") or ""),
            )
        )

    return run


def _list_deploys(search: CodeSearch) -> ToolFn:
    def run(params: Mapping[str, Any]) -> object:
        return list(search.recent_deploys(service=str(params.get("service") or "")))

    return run


def _retrieve(retrieve: KnowledgeRetrieve) -> ToolFn:
    def run(params: Mapping[str, Any]) -> object:
        return _retrieve_runbooks_and_incidents(
            retrieve,
            query=str(params.get("query") or ""),
            service=str(params.get("service") or ""),
            scenario=str(params.get("scenario") or ""),
        )

    return run
