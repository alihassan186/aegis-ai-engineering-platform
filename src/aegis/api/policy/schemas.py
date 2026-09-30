"""HTTP schemas for policy rules. Same error envelope as other v1 routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aegis.api.incidents.schemas import ErrorResponse
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.policy.entity import PolicyRule


class CreatePolicyRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=128)
    action_class: ActionClass
    scope: str = Field(min_length=1, max_length=255)
    allowed: bool
    reason: str = Field(default="", max_length=255)


class PatchPolicyRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str | None = Field(default=None, min_length=1, max_length=128)
    action_class: ActionClass | None = None
    scope: str | None = Field(default=None, min_length=1, max_length=255)
    allowed: bool | None = None
    reason: str | None = Field(default=None, max_length=255)


class PolicyRuleBody(BaseModel):
    id: UUID
    tool_name: str
    action_class: ActionClass
    scope: str
    allowed: bool
    reason: str
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class PolicyRuleResponse(PolicyRuleBody):
    request_id: str


class PolicyRuleListResponse(BaseModel):
    items: list[PolicyRuleBody]
    request_id: str


def policy_body_from_entity(rule: PolicyRule) -> PolicyRuleBody:
    return PolicyRuleBody(
        id=rule.id,
        tool_name=rule.tool_name,
        action_class=rule.action_class,
        scope=rule.scope,
        allowed=rule.allowed,
        reason=rule.reason,
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def policy_response_from_entity(rule: PolicyRule, request_id: str) -> PolicyRuleResponse:
    body = policy_body_from_entity(rule)
    return PolicyRuleResponse(**body.model_dump(), request_id=request_id)


__all__ = [
    "CreatePolicyRuleRequest",
    "ErrorResponse",
    "PatchPolicyRuleRequest",
    "PolicyRuleBody",
    "PolicyRuleListResponse",
    "PolicyRuleResponse",
]
