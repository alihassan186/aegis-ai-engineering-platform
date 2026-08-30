"""API roles (FR-072)."""

from enum import StrEnum


class Role(StrEnum):
    """v0.2 roles. Approver workflow for remediation is v0.9 (FR-073)."""

    VIEWER = "viewer"
    ENGINEER = "engineer"
    APPROVER = "approver"
    ADMIN = "admin"
