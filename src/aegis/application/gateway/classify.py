"""Classify a tool **name**. Never ask the LLM for ``action_class``."""

from __future__ import annotations

from aegis.domain.gateway.enums import ActionClass

READ_TOOLS: frozenset[str] = frozenset(
    {
        "retrieve_knowledge",
        "fetch_signals",
        "search_code",
        "list_deploys",
    }
)

DESTRUCTIVE_TOOLS: frozenset[str] = frozenset(
    {
        "drop_database",
        "delete_rds",
        "kubectl_delete",
        "restart_service",
    }
)

HIGH_RISK_WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "restart_payment",
        "gh_pr_create",
    }
)


def classify(tool_name: str) -> ActionClass | None:
    """Return the registry class, or ``None`` when the name is unknown.

    ``None`` is deny. Caller-supplied ``action_class`` is not an argument here.
    """
    name = tool_name.strip()
    if name in READ_TOOLS:
        return ActionClass.READ
    if name in DESTRUCTIVE_TOOLS:
        return ActionClass.DESTRUCTIVE
    if name in HIGH_RISK_WRITE_TOOLS:
        return ActionClass.HIGH_RISK_WRITE
    return None
