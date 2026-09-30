"""Application agent identities (FR-074, FR-061, NFR-033).

Human JWT roles (``viewer`` / ``engineer`` / ``admin``) are a different plane.
Mixing them with ``agent_id`` is a confused-deputy bug.

This is **not** AWS IAM. Task-role IAM is Phase 6 (steps 6.4 / 6.8). These
ids are minted by the worker when it runs a node — never by Claude.
"""

from collections.abc import Mapping
from enum import StrEnum


class AgentIdentity(StrEnum):
    """One service account per graph role. No shared ``system`` id."""

    KNOWLEDGE = "knowledge"
    OBSERVABILITY = "observability"
    CODE = "code"
    COMMANDER = "commander"
    RCA = "rca"


AGENT_TOOL_GRANTS: Mapping[AgentIdentity, frozenset[str]] = {
    AgentIdentity.KNOWLEDGE: frozenset({"retrieve_knowledge"}),
    AgentIdentity.OBSERVABILITY: frozenset({"fetch_signals"}),
    AgentIdentity.CODE: frozenset({"search_code", "list_deploys"}),
    AgentIdentity.COMMANDER: frozenset(),
    AgentIdentity.RCA: frozenset(),
}


def parse_agent_identity(value: str) -> AgentIdentity | None:
    try:
        return AgentIdentity(value.strip())
    except ValueError:
        return None


def agent_may_invoke(agent_id: str, tool_name: str) -> bool:
    """Least-privilege grant check. Unknown ids cannot invoke anything."""
    identity = parse_agent_identity(agent_id)
    if identity is None:
        return False
    return tool_name in AGENT_TOOL_GRANTS[identity]
