"""In-process snapshot of POLICY_RULE. Invalidate by replacing, not mutating."""

from __future__ import annotations

from collections.abc import Sequence

from aegis.domain.policy.entity import PolicyRule

_rules: tuple[PolicyRule, ...] | None = None


def snapshot_policy_rules() -> tuple[PolicyRule, ...] | None:
    """``None`` means this process has not loaded DB rules yet."""
    return _rules


def replace_policy_rules(rules: Sequence[PolicyRule]) -> None:
    """Atomic replace. Prefer this over clearing (stale allow is a security bug)."""
    global _rules
    _rules = tuple(rules)


def clear_policy_rule_cache() -> None:
    """Test helper. Production writes should ``replace_policy_rules`` with a full list."""
    global _rules
    _rules = None
