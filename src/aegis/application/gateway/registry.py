"""Name → action class and runners. Gateway never imports tool clients (FR-060)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from aegis.application.gateway.classify import READ_TOOLS
from aegis.application.gateway.limits import CircuitBreaker, ToolLimits, harden_tool
from aegis.core.protocols import CodeSearch, ObservabilitySource
from aegis.domain.gateway.enums import ActionClass
from aegis.tools.fetch_signals import FetchSignalsParams, make_fetch_signals
from aegis.tools.list_deploys import ListDeploysParams, make_list_deploys
from aegis.tools.retrieve_knowledge import (
    KnowledgeRetrieve,
    RetrieveKnowledgeParams,
    make_retrieve_knowledge,
)
from aegis.tools.search_code import SearchCodeParams, make_search_code

READ_TOOL_NAMES: frozenset[str] = READ_TOOLS

# v0.6: capability registry is read-only. Writes stay unclassified here.
WRITE_TOOL_NAMES: frozenset[str] = frozenset()

TOOL_ACTION_CLASS: Mapping[str, ActionClass] = {name: ActionClass.READ for name in READ_TOOL_NAMES}


# Wrapper-level allowlist of parameter keys (5.10). Derived from the tool models so the
# two cannot drift. An unknown key such as ``url`` is a gadget, not an option.
TOOL_PARAM_KEYS: Mapping[str, frozenset[str]] = {
    "fetch_signals": frozenset(FetchSignalsParams.model_fields),
    "search_code": frozenset(SearchCodeParams.model_fields),
    "list_deploys": frozenset(ListDeploysParams.model_fields),
    "retrieve_knowledge": frozenset(RetrieveKnowledgeParams.model_fields),
}


def action_class_for(tool_name: str) -> ActionClass | None:
    """Default class from the registry. Unknown names are ``None`` (deny)."""
    return TOOL_ACTION_CLASS.get(tool_name.strip())


def runners_for_ports(
    *,
    observability: ObservabilitySource,
    code_search: CodeSearch,
    retrieve: KnowledgeRetrieve | None = None,
    limits: ToolLimits | None = None,
    breaker: CircuitBreaker | None = None,
) -> dict[str, Callable[[Mapping[str, Any]], Any]]:
    """Bind 4.5 ports to the four named read tools. Every runner is hardened (5.10)."""
    raw: dict[str, Callable[[Mapping[str, Any]], Any]] = {
        "fetch_signals": make_fetch_signals(observability),
        "search_code": make_search_code(code_search),
        "list_deploys": make_list_deploys(code_search),
    }
    if retrieve is not None:
        raw["retrieve_knowledge"] = make_retrieve_knowledge(retrieve)
    return harden_runners(raw, limits=limits, breaker=breaker)


def harden_runners(
    runners: Mapping[str, Callable[[Mapping[str, Any]], Any]],
    *,
    limits: ToolLimits | None = None,
    breaker: CircuitBreaker | None = None,
) -> dict[str, Callable[[Mapping[str, Any]], Any]]:
    """Wrap each callable with timeout, caps, key allowlist, and the shared breaker."""
    resolved = limits or ToolLimits.from_settings()
    shared = breaker or CircuitBreaker(
        threshold=resolved.breaker_threshold,
        cooldown_seconds=resolved.breaker_cooldown_seconds,
    )
    return {
        name: harden_tool(
            name,
            fn,
            limits=resolved,
            breaker=shared,
            allowed_params=TOOL_PARAM_KEYS.get(name),
        )
        for name, fn in runners.items()
    }
