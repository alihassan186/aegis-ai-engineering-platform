"""v0.2 incident permission matrix (FR-071, FR-072)."""

from aegis.domain.auth import Permission, Role, has_permission


def test_viewer_is_read_only() -> None:
    assert has_permission(Role.VIEWER, Permission.READ_INCIDENT)
    assert not has_permission(Role.VIEWER, Permission.CREATE_INCIDENT)
    assert not has_permission(Role.VIEWER, Permission.TRANSITION_INCIDENT)


def test_write_roles_can_create_and_transition() -> None:
    for role in (Role.ENGINEER, Role.APPROVER, Role.ADMIN):
        assert has_permission(role, Permission.CREATE_INCIDENT)
        assert has_permission(role, Permission.READ_INCIDENT)
        assert has_permission(role, Permission.TRANSITION_INCIDENT)
