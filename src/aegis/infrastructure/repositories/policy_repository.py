"""SQLAlchemy ``PolicyRepository`` (ADR-001, ADR-002)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.domain.gateway.enums import ActionClass
from aegis.domain.policy.entity import PolicyRule, PolicyRuleChange
from aegis.infrastructure.database.models.policy import PolicyRuleModel
from aegis.infrastructure.database.models.policy_change import PolicyRuleChangeModel
from aegis.shared.exceptions import NotFoundError, ValidationError


class SqlAlchemyPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_rules(self) -> list[PolicyRule]:
        stmt = select(PolicyRuleModel).order_by(
            PolicyRuleModel.tool_name.asc(),
            PolicyRuleModel.scope.asc(),
            PolicyRuleModel.id.asc(),
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]

    async def get(self, rule_id: UUID) -> PolicyRule | None:
        row = await self._session.get(PolicyRuleModel, rule_id)
        return None if row is None else _to_domain(row)

    async def add(self, rule: PolicyRule) -> PolicyRule:
        self._session.add(_to_orm(rule))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ValidationError(
                "a rule already exists for this tool, action class, and scope."
            ) from exc
        return rule

    async def save(self, rule: PolicyRule) -> PolicyRule:
        row = await self._session.get(PolicyRuleModel, rule.id)
        if row is None:
            raise NotFoundError(f"Policy rule '{rule.id}' was not found.")
        row.tool_name = rule.tool_name
        row.action_class = rule.action_class.value
        row.scope = rule.scope
        row.allowed = rule.allowed
        row.reason = rule.reason
        row.updated_by = rule.updated_by
        row.updated_at = rule.updated_at
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ValidationError(
                "a rule already exists for this tool, action class, and scope."
            ) from exc
        return rule

    async def delete(self, rule_id: UUID) -> None:
        row = await self._session.get(PolicyRuleModel, rule_id)
        if row is None:
            raise NotFoundError(f"Policy rule '{rule_id}' was not found.")
        await self._session.delete(row)
        await self._session.flush()

    async def append_change(self, change: PolicyRuleChange) -> None:
        self._session.add(
            PolicyRuleChangeModel(
                id=change.id,
                rule_id=change.rule_id,
                actor=change.actor,
                action=change.action,
                before=change.before,
                after=change.after,
                created_at=change.created_at,
            )
        )
        await self._session.flush()


def _to_orm(rule: PolicyRule) -> PolicyRuleModel:
    return PolicyRuleModel(
        id=rule.id,
        tool_name=rule.tool_name,
        action_class=rule.action_class.value,
        scope=rule.scope,
        allowed=rule.allowed,
        reason=rule.reason,
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _to_domain(row: PolicyRuleModel) -> PolicyRule:
    return PolicyRule(
        id=row.id,
        tool_name=row.tool_name,
        action_class=ActionClass(row.action_class),
        scope=row.scope,
        allowed=row.allowed,
        reason=row.reason,
        created_by=row.created_by,
        updated_by=row.updated_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
