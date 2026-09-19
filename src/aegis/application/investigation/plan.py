"""Deterministic commander policy (FR-021). No LangGraph, no tools, no LLM.

The commander *node* is a thin adapter. This module is the product: given
scenario, hops, evidence shape, and optional wall clock, choose the next
action. Tests call ``next_action`` directly — compiling the graph is not
required.

Priority (first match wins):

1. ``hops > MAX_HOPS`` → escalate (``max_hops``, RISK-010)
2. elapsed > ``MAX_DURATION`` → escalate (``max_duration``, FR-026)
3. enough evidence (count, or required kinds for ``db_exhaustion``) → synthesize
4. FR-083 first-specialist table, with “already collected this kind” so
   specialists do not ping-pong
5. default → knowledge (unknown / ``unspecified``)

``low_confidence`` (FR-025) is a domain reason, not fired here — there is
no RCA score until Step 4.8. An LLM router later must keep the same caps.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from aegis.application.investigation.state import (
    ENOUGH_EVIDENCE,
    MAX_DURATION,
    MAX_HOPS,
)
from aegis.domain.investigation import EscalateReason

KIND_OBSERVABILITY = "observability"
KIND_KNOWLEDGE = "knowledge"
KIND_CODE = "code"

_OBS_FIRST = frozenset({"latency_spike", "memory_leak", "queue_backlog"})
_DB_REQUIRED = frozenset({KIND_OBSERVABILITY, KIND_KNOWLEDGE})


class NextAction(StrEnum):
    """Graph destinations the commander may choose. ``fanout`` is routing sugar."""

    OBSERVABILITY = "observability"
    KNOWLEDGE = "knowledge"
    CODE = "code"
    FANOUT = "fanout"
    SYNTHESIZE = "synthesize"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class PlanDecision:
    next_agent: NextAction
    escalate_reason: EscalateReason | None = None


def evidence_kinds(evidence: Sequence[object]) -> frozenset[str]:
    """Classify structured items (``collector``) or legacy prefix strings."""
    kinds: set[str] = set()
    for item in evidence:
        collector = _collector_of(item)
        if collector:
            kinds.add(collector)
    return frozenset(kinds)


def enough_evidence(scenario: str, evidence: Sequence[object]) -> bool:
    """v0.5 sufficiency: N items, or obs+knowledge for ``db_exhaustion``."""
    kinds = evidence_kinds(evidence)
    if scenario == "db_exhaustion":
        return _DB_REQUIRED <= kinds
    return len(evidence) >= ENOUGH_EVIDENCE


def next_action(
    *,
    scenario: str,
    hops: int,
    evidence: Sequence[object] = (),
    started_at: str | None = None,
    now: datetime | None = None,
    failed_steps: Sequence[str] = (),
) -> PlanDecision:
    """Return the next node. ``hops`` is the *upcoming* commander visit (1-based)."""
    clock = _as_utc(now) if now is not None else datetime.now(timezone.utc)

    if hops > MAX_HOPS:
        return PlanDecision(NextAction.ESCALATE, EscalateReason.MAX_HOPS)
    if _exceeded_duration(started_at, clock):
        return PlanDecision(NextAction.ESCALATE, EscalateReason.MAX_DURATION)
    if enough_evidence(scenario, evidence):
        return PlanDecision(NextAction.SYNTHESIZE)

    specialist = _first_specialist(scenario)
    kinds = evidence_kinds(evidence)
    if _failure_blocks(specialist, failed_steps, kinds):
        return PlanDecision(NextAction.ESCALATE, EscalateReason.AGENT_FAILURE)

    if specialist is NextAction.ESCALATE:
        return PlanDecision(NextAction.ESCALATE, EscalateReason.DEPENDENCY_FAILURE)
    if specialist is NextAction.FANOUT:
        return _fanout_or_remaining(kinds)
    if _already_collected(specialist, kinds):
        return PlanDecision(NextAction.SYNTHESIZE)
    return PlanDecision(specialist)


def _first_specialist(scenario: str) -> NextAction:
    if scenario == "dependency_failure":
        return NextAction.ESCALATE
    if scenario == "db_exhaustion":
        return NextAction.FANOUT
    if scenario == "bad_deployment":
        return NextAction.CODE
    if scenario in _OBS_FIRST:
        return NextAction.OBSERVABILITY
    return NextAction.KNOWLEDGE


def _fanout_or_remaining(kinds: frozenset[str]) -> PlanDecision:
    has_obs = KIND_OBSERVABILITY in kinds
    has_kb = KIND_KNOWLEDGE in kinds
    if has_obs and has_kb:
        return PlanDecision(NextAction.SYNTHESIZE)
    if has_obs:
        return PlanDecision(NextAction.KNOWLEDGE)
    if has_kb:
        return PlanDecision(NextAction.OBSERVABILITY)
    return PlanDecision(NextAction.FANOUT)


def _collector_of(item: object) -> str | None:
    aliases = {
        "observability": KIND_OBSERVABILITY,
        "obs": KIND_OBSERVABILITY,
        "knowledge": KIND_KNOWLEDGE,
        "kb-stub": KIND_KNOWLEDGE,
        "kb": KIND_KNOWLEDGE,
        "code": KIND_CODE,
    }
    if isinstance(item, Mapping):
        raw = str(item.get("collector") or "").strip().lower()
        return aliases.get(raw)
    prefix = str(item).split(":", 1)[0]
    return aliases.get(prefix)


def _failure_blocks(
    specialist: NextAction,
    failed_steps: Sequence[str],
    kinds: frozenset[str],
) -> bool:
    failed = {step.strip().lower() for step in failed_steps}
    if specialist is NextAction.FANOUT:
        need_obs = KIND_OBSERVABILITY not in kinds
        need_kb = KIND_KNOWLEDGE not in kinds
        return (need_obs and "observability" in failed) or (need_kb and "knowledge" in failed)
    name = {
        NextAction.OBSERVABILITY: "observability",
        NextAction.KNOWLEDGE: "knowledge",
        NextAction.CODE: "code",
    }.get(specialist)
    return bool(name and name in failed)


def _already_collected(specialist: NextAction, kinds: frozenset[str]) -> bool:
    if specialist is NextAction.OBSERVABILITY:
        return KIND_OBSERVABILITY in kinds
    if specialist is NextAction.CODE:
        return KIND_CODE in kinds
    if specialist is NextAction.KNOWLEDGE:
        return KIND_KNOWLEDGE in kinds
    return False


def _exceeded_duration(started_at: str | None, now: datetime) -> bool:
    if not started_at or not started_at.strip():
        return False
    try:
        start = _parse_started_at(started_at)
    except ValueError:
        return False
    return now - start > MAX_DURATION


def _parse_started_at(started_at: str) -> datetime:
    text = started_at.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
