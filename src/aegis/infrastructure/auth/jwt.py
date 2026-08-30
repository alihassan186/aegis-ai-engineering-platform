"""JWT create and verify (FR-070, THR-001, THR-013)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from aegis.config.settings import Settings
from aegis.domain.auth.enums import Role

ALGORITHM = "HS256"
ISSUER = "aegis"


class JwtNotConfiguredError(RuntimeError):
    """Raised when AEGIS_JWT_SECRET is missing."""


class InvalidAccessTokenError(ValueError):
    """Raised when a bearer token is expired, forged, or malformed."""


@dataclass(frozen=True, slots=True)
class TokenPayload:
    subject: str
    role: Role


def create_access_token(
    settings: Settings,
    *,
    subject: str,
    role: Role,
    expires_in: int | None = None,
) -> str:
    secret = _require_secret(settings)
    lifetime = settings.jwt_expire_seconds if expires_in is None else expires_in
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(seconds=lifetime),
        "iss": ISSUER,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> TokenPayload:
    secret = _require_secret(settings)
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidAccessTokenError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidAccessTokenError("Access token is invalid.") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise InvalidAccessTokenError("Access token is missing subject.")

    role_value = payload.get("role")
    if not isinstance(role_value, str):
        raise InvalidAccessTokenError("Access token has an invalid role.")
    try:
        role = Role(role_value)
    except ValueError as exc:
        raise InvalidAccessTokenError("Access token has an invalid role.") from exc

    return TokenPayload(subject=subject.strip(), role=role)


def _require_secret(settings: Settings) -> str:
    secret = settings.jwt_secret.strip()
    if not secret:
        raise JwtNotConfiguredError(
            "JWT is not configured. Set AEGIS_JWT_SECRET (never hardcode secrets)."
        )
    return secret
