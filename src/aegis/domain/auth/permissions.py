"""Role-to-permission matrix for incidents and investigations (FR-071)."""

from collections.abc import Mapping
from enum import StrEnum

from aegis.domain.auth.enums import Role


class Permission(StrEnum):
    CREATE_INCIDENT = "create_incident"
    READ_INCIDENT = "read_incident"
    TRANSITION_INCIDENT = "transition_incident"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    VIEW_INVESTIGATION = "view_investigation"
    REVIEW_RCA = "review_rca"
    CONTROL_INVESTIGATION = "control_investigation"
    ADD_EVIDENCE = "add_evidence"


_INVESTIGATION_WRITE = frozenset(
    {
        Permission.VIEW_INVESTIGATION,
        Permission.REVIEW_RCA,
        Permission.CONTROL_INVESTIGATION,
        Permission.ADD_EVIDENCE,
    }
)

ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset(
        {
            Permission.READ_INCIDENT,
            Permission.RETRIEVE_KNOWLEDGE,
            Permission.VIEW_INVESTIGATION,
        }
    ),
    Role.ENGINEER: frozenset[Permission](
        {
            Permission.CREATE_INCIDENT,
            Permission.READ_INCIDENT,
            Permission.TRANSITION_INCIDENT,
            Permission.RETRIEVE_KNOWLEDGE,
            *_INVESTIGATION_WRITE,
        }
    ),
    Role.APPROVER: frozenset(
        {
            Permission.CREATE_INCIDENT,
            Permission.READ_INCIDENT,
            Permission.TRANSITION_INCIDENT,
            Permission.RETRIEVE_KNOWLEDGE,
            *_INVESTIGATION_WRITE,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.CREATE_INCIDENT,
            Permission.READ_INCIDENT,
            Permission.TRANSITION_INCIDENT,
            Permission.RETRIEVE_KNOWLEDGE,
            *_INVESTIGATION_WRITE,
        }
    ),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
