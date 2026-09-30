"""Authentication and authorization domain types (FR-070–FR-074)."""

from aegis.domain.auth.agent_identity import (
    AGENT_TOOL_GRANTS,
    AgentIdentity,
    agent_may_invoke,
    parse_agent_identity,
)
from aegis.domain.auth.enums import Role
from aegis.domain.auth.permissions import ROLE_PERMISSIONS, Permission, has_permission

__all__ = [
    "AGENT_TOOL_GRANTS",
    "AgentIdentity",
    "Permission",
    "ROLE_PERMISSIONS",
    "Role",
    "agent_may_invoke",
    "has_permission",
    "parse_agent_identity",
]
