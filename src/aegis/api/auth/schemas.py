"""Dev-only token request/response. Production authenticates via an IdP."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from aegis.domain.auth.enums import Role


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    role: Role
    request_id: str
