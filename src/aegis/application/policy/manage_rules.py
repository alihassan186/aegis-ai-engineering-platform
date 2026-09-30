"""Admin CRUD for policy rules (FR-066). API stays thin."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import UUID

from aegis.core.protocols import PolicyRepository
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.policy.entity import PolicyRule, PolicyRuleChange
from aegis.shared.exceptions import NotFoundError

OnChange = Callable[[Sequence[PolicyRule]], None]


class ManageRules:
    def __init__(
        self,
        repository: PolicyRepository,
        *,
        on_change: OnChange | None = None,
    ) -> None:
        self._repository = repository
        self._on_change = on_change

    async def list_rules(self) -> list[PolicyRule]:
        return await self._repository.list_rules()

    async def get(self, rule_id: UUID) -> PolicyRule:
        rule = await self._repository.get(rule_id)
        if rule is None:
            raise NotFoundError(f"Policy rule '{rule_id}' was not found.")
        return rule

    async def create(
        self,
        *,
        actor: str,
        tool_name: str,
        action_class: ActionClass | str,
        scope: str,
        allowed: bool,
        reason: str = "",
    ) -> PolicyRule:
        rule = PolicyRule.create(
            tool_name=tool_name,
            action_class=action_class,
            scope=scope,
            allowed=allowed,
            reason=reason,
            actor=actor,
        )
        persisted = await self._repository.add(rule)
        await self._repository.append_change(
            PolicyRuleChange.record(
                actor=actor,
                action="created",
                rule_id=persisted.id,
                before=None,
                after=persisted.snapshot(),
            )
        )
        await self._publish()
        return persisted

    async def update(
        self,
        rule_id: UUID,
        *,
        actor: str,
        tool_name: str | None = None,
        action_class: ActionClass | str | None = None,
        scope: str | None = None,
        allowed: bool | None = None,
        reason: str | None = None,
    ) -> PolicyRule:
        existing = await self.get(rule_id)
        updated = existing.replace(
            actor=actor,
            tool_name=tool_name,
            action_class=action_class,
            scope=scope,
            allowed=allowed,
            reason=reason,
        )
        persisted = await self._repository.save(updated)
        await self._repository.append_change(
            PolicyRuleChange.record(
                actor=actor,
                action="updated",
                rule_id=persisted.id,
                before=existing.snapshot(),
                after=persisted.snapshot(),
            )
        )
        await self._publish()
        return persisted

    async def delete(self, rule_id: UUID, *, actor: str) -> None:
        existing = await self.get(rule_id)
        await self._repository.delete(rule_id)
        await self._repository.append_change(
            PolicyRuleChange.record(
                actor=actor,
                action="deleted",
                rule_id=existing.id,
                before=existing.snapshot(),
                after=None,
            )
        )
        await self._publish()

    async def _publish(self) -> None:
        if self._on_change is None:
            return
        self._on_change(await self._repository.list_rules())
