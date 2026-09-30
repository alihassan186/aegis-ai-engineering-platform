"""Deterministic policy evaluation (FR-067). Default deny. Most specific wins."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from aegis.domain.gateway.enums import ActionClass
from aegis.domain.policy.entity import WILDCARD, PolicyRule


@dataclass(frozen=True, slots=True)
class PolicyVerdict:
    allowed: bool
    reason: str
    rule_id: UUID | None
    action_class: ActionClass | None


def evaluate_policy(
    rules: Sequence[PolicyRule],
    *,
    tool_name: str,
    action_class: ActionClass | None,
    agent_id: str,
    service: str = "",
) -> PolicyVerdict:
    """Pick the most specific matching rule. No match is deny. Destructive never allows."""
    if action_class is ActionClass.DESTRUCTIVE:
        return PolicyVerdict(
            allowed=False,
            reason="denied:destructive",
            rule_id=None,
            action_class=action_class,
        )

    scored: list[tuple[int, PolicyRule]] = []
    for rule in rules:
        score = _specificity(rule, tool_name, action_class, agent_id, service)
        if score is not None:
            scored.append((score, rule))

    if not scored:
        reason = "denied:unknown_tool" if action_class is None else "denied:default"
        return PolicyVerdict(
            allowed=False,
            reason=reason,
            rule_id=None,
            action_class=action_class,
        )

    best = max(item[0] for item in scored)
    tied = [rule for score, rule in scored if score == best]
    winner = _fail_closed(tied)
    if winner.action_class is ActionClass.DESTRUCTIVE or not winner.allowed:
        return PolicyVerdict(
            allowed=False,
            reason=_deny_reason(winner),
            rule_id=winner.id,
            action_class=winner.action_class,
        )
    return PolicyVerdict(
        allowed=True,
        reason=winner.reason or "allowed:policy",
        rule_id=winner.id,
        action_class=winner.action_class,
    )


def _specificity(
    rule: PolicyRule,
    tool_name: str,
    action_class: ActionClass | None,
    agent_id: str,
    service: str,
) -> int | None:
    if action_class is not None and rule.action_class is not action_class:
        return None
    if rule.tool_name == tool_name:
        tool_points = 4
    elif rule.tool_name == WILDCARD:
        tool_points = 1
    else:
        return None
    if rule.scope == agent_id:
        scope_points = 3
    elif service and rule.scope == service:
        scope_points = 2
    elif rule.scope == WILDCARD:
        scope_points = 1
    else:
        return None
    return tool_points * 10 + scope_points


def _fail_closed(tied: Sequence[PolicyRule]) -> PolicyRule:
    denies = [rule for rule in tied if not rule.allowed]
    if denies:
        return denies[0]
    return tied[0]


def _deny_reason(rule: PolicyRule) -> str:
    if rule.action_class is ActionClass.DESTRUCTIVE:
        return "denied:destructive"
    if rule.reason.startswith("denied:"):
        return rule.reason
    return "denied:policy"
