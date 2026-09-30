"""GET/POST/PATCH/DELETE /api/v1/policy/rules — JWT admin only (FR-066)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from aegis.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_manage_rules,
    require_permission,
)
from aegis.api.policy.schemas import (
    CreatePolicyRuleRequest,
    ErrorResponse,
    PatchPolicyRuleRequest,
    PolicyRuleListResponse,
    PolicyRuleResponse,
    policy_body_from_entity,
    policy_response_from_entity,
)
from aegis.api.request_id import request_id_from
from aegis.application.policy.manage_rules import ManageRules
from aegis.domain.auth.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get(
    "",
    response_model=PolicyRuleListResponse,
    responses=_ERROR_RESPONSES,
    summary="List tool policy rules",
)
async def list_policy_rules(
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.MANAGE_POLICY)),
    use_case: ManageRules = Depends(get_manage_rules),
) -> PolicyRuleListResponse:
    rules = await use_case.list_rules()
    return PolicyRuleListResponse(
        items=[policy_body_from_entity(rule) for rule in rules],
        request_id=request_id_from(request),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PolicyRuleResponse,
    responses=_ERROR_RESPONSES,
    summary="Create a tool policy rule",
)
async def create_policy_rule(
    body: CreatePolicyRuleRequest,
    request: Request,
    response: Response,
    user: CurrentUser = Depends(require_permission(Permission.MANAGE_POLICY)),
    use_case: ManageRules = Depends(get_manage_rules),
) -> PolicyRuleResponse:
    rule = await use_case.create(
        actor=user.subject,
        tool_name=body.tool_name,
        action_class=body.action_class,
        scope=body.scope,
        allowed=body.allowed,
        reason=body.reason,
    )
    response.headers["Location"] = f"/api/v1/policy/rules/{rule.id}"
    return policy_response_from_entity(rule, request_id_from(request))


@router.get(
    "/{rule_id}",
    response_model=PolicyRuleResponse,
    responses=_ERROR_RESPONSES,
    summary="Get one tool policy rule",
)
async def get_policy_rule(
    rule_id: UUID,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.MANAGE_POLICY)),
    use_case: ManageRules = Depends(get_manage_rules),
) -> PolicyRuleResponse:
    rule = await use_case.get(rule_id)
    return policy_response_from_entity(rule, request_id_from(request))


@router.patch(
    "/{rule_id}",
    response_model=PolicyRuleResponse,
    responses=_ERROR_RESPONSES,
    summary="Update a tool policy rule",
)
async def patch_policy_rule(
    rule_id: UUID,
    body: PatchPolicyRuleRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission(Permission.MANAGE_POLICY)),
    use_case: ManageRules = Depends(get_manage_rules),
) -> PolicyRuleResponse:
    rule = await use_case.update(
        rule_id,
        actor=user.subject,
        tool_name=body.tool_name,
        action_class=body.action_class,
        scope=body.scope,
        allowed=body.allowed,
        reason=body.reason,
    )
    return policy_response_from_entity(rule, request_id_from(request))


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERROR_RESPONSES,
    summary="Delete a tool policy rule",
)
async def delete_policy_rule(
    rule_id: UUID,
    user: CurrentUser = Depends(require_permission(Permission.MANAGE_POLICY)),
    use_case: ManageRules = Depends(get_manage_rules),
) -> None:
    await use_case.delete(rule_id, actor=user.subject)
