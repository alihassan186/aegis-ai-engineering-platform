"""In-process snapshot of POLICY_RULE. Invalidate by replacing, not mutating."""

from __future__ import annotations

from collections.abc import Sequence

from aegis.application.policy.version import policy_version_for
from aegis.domain.policy.entity import PolicyRule

_rules: tuple[PolicyRule, ...] | None = None
_version: str | None = None


def snapshot_policy_rules() -> tuple[PolicyRule, ...] | None:
    """``None`` means this process has not loaded DB rules yet."""
    return _rules


def snapshot_policy_version() -> str | None:
    """Version of the cached rules (5.11). ``None`` while the cache is cold."""
    return _version


def replace_policy_rules(rules: Sequence[PolicyRule]) -> None:
    """Atomic replace. Prefer this over clearing (stale allow is a security bug)."""
    global _rules, _version
    loaded = tuple(rules)
    _version = policy_version_for(loaded)
    _rules = loaded


def clear_policy_rule_cache() -> None:
    """Test helper. Production writes should ``replace_policy_rules`` with a full list."""
    global _rules, _version
    _rules = None
    _version = None
