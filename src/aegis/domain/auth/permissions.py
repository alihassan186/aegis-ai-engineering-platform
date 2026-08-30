"""Role-to-permission matrix for incidents (FR-071, v0.2)."""

from collections.abc import Mapping
from enum import StrEnum

from aegis.domain.auth.enums import Role


class Permission(StrEnum):
    CREATE_INCIDENT = "create_incident"
    READ_INCIDENT = "read_incident"
    TRANSITION_INCIDENT = "transition_incident"


ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({Permission.READ_INCIDENT}),
    Role.ENGINEER: frozenset(
        {
            Permission.CREATE_INCIDENT,
            Permission.READ_INCIDENT,
            Permission.TRANSITION_INCIDENT,
        }
    ),
    Role.APPROVER: frozenset(
        {
            Permission.CREATE_INCIDENT,
            Permission.READ_INCIDENT,
            Permission.TRANSITION_INCIDENT,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.CREATE_INCIDENT,
            Permission.READ_INCIDENT,
            Permission.TRANSITION_INCIDENT,
        }
    ),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
