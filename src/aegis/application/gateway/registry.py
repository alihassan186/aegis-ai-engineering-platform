"""Name → action class and runners. Gateway never imports tool clients (FR-060)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from aegis.application.gateway.classify import READ_TOOLS
from aegis.core.protocols import CodeSearch, ObservabilitySource
from aegis.domain.gateway.enums import ActionClass
from aegis.tools.fetch_signals import make_fetch_signals
from aegis.tools.list_deploys import make_list_deploys
from aegis.tools.retrieve_knowledge import KnowledgeRetrieve, make_retrieve_knowledge
from aegis.tools.search_code import make_search_code

READ_TOOL_NAMES: frozenset[str] = READ_TOOLS

# v0.6: capability registry is read-only. Writes stay unclassified here.
WRITE_TOOL_NAMES: frozenset[str] = frozenset()

TOOL_ACTION_CLASS: Mapping[str, ActionClass] = {name: ActionClass.READ for name in READ_TOOL_NAMES}


def action_class_for(tool_name: str) -> ActionClass | None:
    """Default class from the registry. Unknown names are ``None`` (deny)."""
    return TOOL_ACTION_CLASS.get(tool_name.strip())


def runners_for_ports(
    *,
    observability: ObservabilitySource,
    code_search: CodeSearch,
    retrieve: KnowledgeRetrieve | None = None,
) -> dict[str, Callable[[Mapping[str, Any]], Any]]:
    """Bind 4.5 ports to the four named read tools."""
    tools: dict[str, Callable[[Mapping[str, Any]], Any]] = {
        "fetch_signals": make_fetch_signals(observability),
        "search_code": make_search_code(code_search),
        "list_deploys": make_list_deploys(code_search),
    }
    if retrieve is not None:
        tools["retrieve_knowledge"] = make_retrieve_knowledge(retrieve)
    return tools
