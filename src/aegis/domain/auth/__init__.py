"""Authentication and authorization domain types (FR-070–FR-072)."""

from aegis.domain.auth.enums import Role
from aegis.domain.auth.permissions import ROLE_PERMISSIONS, Permission, has_permission

__all__ = [
    "Permission",
    "ROLE_PERMISSIONS",
    "Role",
    "has_permission",
]
