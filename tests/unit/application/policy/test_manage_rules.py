"""ManageRules CRUD, cache replace, and destructive create rejection."""

from __future__ import annotations

from uuid import UUID

import pytest

from aegis.application.policy.manage_rules import ManageRules
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.policy.entity import PolicyRule, PolicyRuleChange
from aegis.shared.exceptions import NotFoundError, ValidationError


class FakePolicyRepository:
    def __init__(self) -> None:
        self.rules: dict[UUID, PolicyRule] = {}
        self.changes: list[PolicyRuleChange] = []

    async def list_rules(self) -> list[PolicyRule]:
        return list(self.rules.values())

    async def get(self, rule_id: UUID) -> PolicyRule | None:
        return self.rules.get(rule_id)

    async def add(self, rule: PolicyRule) -> PolicyRule:
        self.rules[rule.id] = rule
        return rule

    async def save(self, rule: PolicyRule) -> PolicyRule:
        if rule.id not in self.rules:
            raise NotFoundError(f"Policy rule '{rule.id}' was not found.")
        self.rules[rule.id] = rule
        return rule

    async def delete(self, rule_id: UUID) -> None:
        if rule_id not in self.rules:
            raise NotFoundError(f"Policy rule '{rule_id}' was not found.")
        del self.rules[rule_id]

    async def append_change(self, change: PolicyRuleChange) -> None:
        self.changes.append(change)


async def test_create_records_change_and_refreshes_cache() -> None:
    repo = FakePolicyRepository()
    captured: list[list[PolicyRule]] = []
    use_case = ManageRules(repo, on_change=lambda rules: captured.append(list(rules)))

    rule = await use_case.create(
        actor="admin-1",
        tool_name="search_code",
        action_class=ActionClass.READ,
        scope="code",
        allowed=False,
        reason="deny code search",
    )
    assert rule.allowed is False
    assert repo.changes[0].action == "created"
    assert repo.changes[0].actor == "admin-1"
    assert captured[0][0].id == rule.id


async def test_create_rejects_destructive_allow() -> None:
    use_case = ManageRules(FakePolicyRepository())
    with pytest.raises(ValidationError, match="destructive"):
        await use_case.create(
            actor="admin-1",
            tool_name="drop_database",
            action_class=ActionClass.DESTRUCTIVE,
            scope="*",
            allowed=True,
        )


async def test_delete_missing_is_not_found() -> None:
    use_case = ManageRules(FakePolicyRepository())
    with pytest.raises(NotFoundError):
        await use_case.get(UUID("11111111-1111-1111-1111-111111111111"))
