"""Kill switch + policy version (Step 5.11, FR-066 / FR-062).

``AEGIS_GUARDRAIL_DENY_ALL`` is an operator env var. It denies every invoke
before any tool runs, and the audit row says which policy version was active.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from aegis.application.audit.append_audit import AppendAudit
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.rate_limit import RateLimiter, ToolRateLimits
from aegis.application.policy.cache import (
    clear_policy_rule_cache,
    replace_policy_rules,
    snapshot_policy_version,
)
from aegis.application.policy.seed import seed_read_rules
from aegis.application.policy.version import policy_version_for
from aegis.config.settings import Settings, guardrail_deny_all_enabled
from aegis.domain.audit.entity import AuditEntry
from aegis.domain.gateway.enums import ActionClass, GatewayVerdict
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.domain.policy.entity import PolicyRule

_INCIDENT = "11111111-1111-1111-1111-111111111111"
_ENV = "AEGIS_GUARDRAIL_DENY_ALL"
_REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(_ENV, raising=False)
    clear_policy_rule_cache()
    yield
    clear_policy_rule_cache()


def _gateway(runs: list[int], audit: AppendAudit | None = None) -> InvokeTool:
    def _retrieve(_params: dict[str, object]) -> str:
        runs.append(1)
        return "runbook excerpt"

    return InvokeTool(
        tools={"retrieve_knowledge": _retrieve},
        audit=audit,
        rate_limiter=RateLimiter(
            limits=ToolRateLimits(
                window_seconds=60.0, per_tool_incident=30, per_agent=90, fail_closed=False
            )
        ),
    )


def _request(**extra: object) -> ToolInvokeRequest:
    return ToolInvokeRequest(
        agent_id="knowledge",
        tool_name="retrieve_knowledge",
        parameters={"query": "latency", **extra},
        incident_id=_INCIDENT,
    )


def test_flag_on_denies_a_listed_read_tool_without_running_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_ENV, "true")
    runs: list[int] = []

    decision = _gateway(runs).invoke(_request())

    assert decision.allowed is False
    assert decision.reason == "denied:kill_switch"
    assert decision.deny_all is True
    assert decision.envelope is None
    assert runs == []


def test_flag_off_allows_the_same_tool() -> None:
    runs: list[int] = []

    decision = _gateway(runs).invoke(_request())

    assert decision.allowed is True
    assert decision.deny_all is False
    assert runs == [1]


def test_flag_is_read_on_every_call(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[int] = []
    gateway = _gateway(runs)

    assert gateway.invoke(_request()).allowed is True
    monkeypatch.setenv(_ENV, "1")
    assert gateway.invoke(_request()).reason == "denied:kill_switch"
    monkeypatch.setenv(_ENV, "false")
    assert gateway.invoke(_request()).allowed is True
    assert runs == [1, 1]


def test_kill_switch_beats_every_other_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "true")
    gateway = _gateway([])
    forged = ToolInvokeRequest(
        agent_id="root",
        tool_name="drop_database",
        parameters={},
        incident_id=_INCIDENT,
    )

    assert gateway.invoke(forged).reason == "denied:kill_switch"


def test_audit_row_has_kill_switch_reason_and_policy_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_ENV, "true")
    audit = AppendAudit()
    decision = _gateway([], audit).invoke(_request())

    [entry] = audit.drain()
    assert entry.reason == "denied:kill_switch"
    assert entry.decision is GatewayVerdict.DENY
    assert entry.deny_all is True
    assert entry.policy_version == policy_version_for(seed_read_rules())
    assert entry.policy_version.startswith("pv1-")
    assert decision.audit_id == str(entry.id)
    assert decision.policy_version == entry.policy_version


def test_allowed_call_is_stamped_with_policy_version_and_deny_all_false() -> None:
    audit = AppendAudit()
    _gateway([], audit).invoke(_request())

    [entry] = audit.drain()
    assert entry.decision is GatewayVerdict.ALLOW
    assert entry.deny_all is False
    assert entry.policy_version


def test_deny_all_cannot_be_set_through_tool_parameters() -> None:
    """An engineer or model cannot flip or clear the switch via parameters."""
    runs: list[int] = []
    gateway = _gateway(runs)

    on_via_params = gateway.invoke(_request(deny_all=True))
    # The extra key reaches the runner (a lambda here) but never the switch.
    assert on_via_params.deny_all is False
    assert on_via_params.reason != "denied:kill_switch"


def test_env_cannot_be_cleared_through_tool_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "true")
    runs: list[int] = []

    decision = _gateway(runs).invoke(_request(deny_all=False))

    assert decision.reason == "denied:kill_switch"
    assert runs == []


def test_policy_version_changes_when_a_rule_is_edited_or_deleted() -> None:
    rules = list(seed_read_rules())
    base = policy_version_for(rules)
    edited = [rules[0].replace(actor="admin", allowed=False), *rules[1:]]

    assert edited[0].version == rules[0].version + 1
    assert policy_version_for(edited) != base
    assert policy_version_for(rules[1:]) != base
    assert policy_version_for(reversed(rules)) == base


def test_gateway_reads_version_with_the_rule_cache() -> None:
    rules = list(seed_read_rules())
    audit = AppendAudit()
    gateway = _gateway([], audit)

    gateway.invoke(_request())
    replace_policy_rules([rules[0].replace(actor="admin", reason="tightened"), *rules[1:]])
    gateway.invoke(_request())

    first, second = audit.drain()
    assert first.policy_version == policy_version_for(rules)
    assert second.policy_version == snapshot_policy_version()
    assert second.policy_version != first.policy_version


def test_denying_rule_edit_shows_up_in_the_next_audit_row() -> None:
    audit = AppendAudit()
    gateway = _gateway([], audit)
    deny_rule = PolicyRule.create(
        tool_name="retrieve_knowledge",
        action_class=ActionClass.READ,
        scope="*",
        allowed=False,
        actor="admin",
    )
    replace_policy_rules([deny_rule])

    decision = gateway.invoke(_request())

    assert decision.allowed is False
    [entry] = audit.drain()
    assert entry.policy_version == snapshot_policy_version()


def test_policy_version_is_part_of_the_hash_only_when_set() -> None:
    plain = AuditEntry.create(
        actor="knowledge",
        action="retrieve_knowledge",
        input={},
        output={},
        decision="allow",
        reason="allowed:read",
        incident_id=_INCIDENT,
        entry_id=UUID(int=1),
        created_at=_fixed_time(),
    )
    versioned = AuditEntry.create(
        actor="knowledge",
        action="retrieve_knowledge",
        input={},
        output={},
        decision="allow",
        reason="allowed:read",
        incident_id=_INCIDENT,
        entry_id=UUID(int=1),
        created_at=_fixed_time(),
        policy_version="pv1-abc",
    )

    assert plain.row_hash != versioned.row_hash


def test_settings_default_is_false_and_env_example_never_enables_it() -> None:
    assert Settings().guardrail_deny_all is False
    assert guardrail_deny_all_enabled() is False
    example = (_REPO_ROOT / "config" / ".env.example").read_text(encoding="utf-8")
    assert "\nAEGIS_GUARDRAIL_DENY_ALL=false" in example
    assert "\nAEGIS_GUARDRAIL_DENY_ALL=true" not in example


def _fixed_time() -> datetime:
    return datetime(2026, 10, 7, tzinfo=timezone.utc)
