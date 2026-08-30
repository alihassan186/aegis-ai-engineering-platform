"""JWT helpers for API tests. Not a product secret."""

from __future__ import annotations

from aegis.config.settings import Settings
from aegis.domain.auth.enums import Role
from aegis.infrastructure.auth.jwt import create_access_token

TEST_JWT_SECRET = "test-only-jwt-secret-not-for-production"


def api_test_settings(
    *,
    environment: str = "test",
    database_url: str = "",
    jwt_secret: str = TEST_JWT_SECRET,
    jwt_expire_seconds: int = 3600,
) -> Settings:
    return Settings(
        environment=environment,
        database_url=database_url,
        jwt_secret=jwt_secret,
        jwt_expire_seconds=jwt_expire_seconds,
    )


def authorization_header(
    role: Role = Role.ENGINEER,
    *,
    subject: str = "test-user",
    settings: Settings | None = None,
    expires_in: int | None = None,
) -> dict[str, str]:
    resolved = settings or api_test_settings()
    token = create_access_token(
        resolved,
        subject=subject,
        role=role,
        expires_in=expires_in,
    )
    return {"Authorization": f"Bearer {token}"}
