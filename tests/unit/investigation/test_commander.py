"""Commander policy (Step 4.4) — no graph compile, no Bedrock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aegis.application.investigation.nodes import commander
from aegis.application.investigation.plan import (
    NextAction,
    enough_evidence,
    next_action,
)
from aegis.application.investigation.state import ENOUGH_EVIDENCE, MAX_DURATION, MAX_HOPS
from aegis.domain.investigation import EscalateReason

_CLOCK = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)

_FR083_FIRST_HOP: tuple[tuple[str, NextAction], ...] = (
    ("latency_spike", NextAction.OBSERVABILITY),
    ("memory_leak", NextAction.OBSERVABILITY),
    ("queue_backlog", NextAction.OBSERVABILITY),
    ("bad_deployment", NextAction.CODE),
    ("db_exhaustion", NextAction.FANOUT),
    ("dependency_failure", NextAction.ESCALATE),
)


@pytest.mark.parametrize(("scenario", "expected"), _FR083_FIRST_HOP)
def test_fr083_first_hop(scenario: str, expected: NextAction) -> None:
    decision = next_action(scenario=scenario, hops=1, evidence=(), now=_CLOCK)

    assert decision.next_agent is expected
    if expected is NextAction.ESCALATE:
        assert decision.escalate_reason is EscalateReason.DEPENDENCY_FAILURE
    else:
        assert decision.escalate_reason is None


def test_unspecified_scenario_defaults_to_knowledge() -> None:
    decision = next_action(scenario="unspecified", hops=1, evidence=(), now=_CLOCK)

    assert decision.next_agent is NextAction.KNOWLEDGE
    assert decision.escalate_reason is None


def test_enough_evidence_routes_to_synthesize() -> None:
    evidence = ["obs:payment:latency_spike"]
    assert len(evidence) >= ENOUGH_EVIDENCE

    decision = next_action(
        scenario="latency_spike",
        hops=2,
        evidence=evidence,
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.SYNTHESIZE


def test_db_exhaustion_needs_both_kinds_not_just_count() -> None:
    obs_only = ["obs:payment:db_exhaustion"]
    assert enough_evidence("latency_spike", obs_only)
    assert not enough_evidence("db_exhaustion", obs_only)

    decision = next_action(
        scenario="db_exhaustion",
        hops=2,
        evidence=obs_only,
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.KNOWLEDGE


def test_db_exhaustion_both_kinds_synthesize() -> None:
    evidence = ["obs:payment:db_exhaustion", "kb-stub:payment:db_exhaustion"]
    assert enough_evidence("db_exhaustion", evidence)

    decision = next_action(
        scenario="db_exhaustion",
        hops=2,
        evidence=evidence,
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.SYNTHESIZE


def test_already_collected_obs_does_not_redelegate() -> None:
    decision = next_action(
        scenario="latency_spike",
        hops=2,
        evidence=["obs:payment:latency_spike"],
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.SYNTHESIZE


def test_hop_overflow_escalates_with_max_hops() -> None:
    decision = next_action(
        scenario="latency_spike",
        hops=MAX_HOPS + 1,
        evidence=(),
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.ESCALATE
    assert decision.escalate_reason is EscalateReason.MAX_HOPS


def test_hop_overflow_beats_enough_evidence() -> None:
    decision = next_action(
        scenario="latency_spike",
        hops=MAX_HOPS + 1,
        evidence=["obs:payment:latency_spike"],
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.ESCALATE
    assert decision.escalate_reason is EscalateReason.MAX_HOPS


def test_elapsed_over_max_duration_escalates() -> None:
    started = (_CLOCK - MAX_DURATION - timedelta(seconds=1)).isoformat()

    decision = next_action(
        scenario="latency_spike",
        hops=1,
        evidence=(),
        started_at=started,
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.ESCALATE
    assert decision.escalate_reason is EscalateReason.MAX_DURATION


def test_elapsed_equal_to_max_duration_does_not_escalate() -> None:
    started = (_CLOCK - MAX_DURATION).isoformat()

    decision = next_action(
        scenario="latency_spike",
        hops=1,
        evidence=(),
        started_at=started,
        now=_CLOCK,
    )

    assert decision.next_agent is NextAction.OBSERVABILITY


def test_hop_overflow_beats_duration() -> None:
    started = (_CLOCK - MAX_DURATION - timedelta(minutes=1)).isoformat()

    decision = next_action(
        scenario="latency_spike",
        hops=MAX_HOPS + 1,
        evidence=(),
        started_at=started,
        now=_CLOCK,
    )

    assert decision.escalate_reason is EscalateReason.MAX_HOPS


def test_deferred_escalate_reasons_exist_for_later_steps() -> None:
    assert EscalateReason.LOW_CONFIDENCE == "low_confidence"
    assert EscalateReason.AGENT_FAILURE == "agent_failure"


def test_commander_node_is_thin_adapter() -> None:
    update = commander(
        {
            "incident_id": "INC-TEST",
            "service": "payment",
            "scenario": "latency_spike",
            "hops": 0,
            "next_agent": "",
            "status": "running",
            "human_decision": "",
            "evidence": [],
            "log": [],
        }
    )

    assert update["hops"] == 1
    assert update["next_agent"] == "observability"
    assert update["escalate_reason"] == ""
    assert update["log"] == ["commander hop=1 → observability"]


def test_commander_node_logs_escalate_reason() -> None:
    update = commander(
        {
            "incident_id": "INC-TEST",
            "service": "order",
            "scenario": "dependency_failure",
            "hops": 0,
            "next_agent": "",
            "status": "running",
            "human_decision": "",
            "evidence": [],
            "log": [],
        }
    )

    assert update["next_agent"] == "escalate"
    assert update["escalate_reason"] == "dependency_failure"
    assert update["log"] == ["commander hop=1 → escalate (dependency_failure)"]
