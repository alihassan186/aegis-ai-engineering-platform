"""Named read tools: registry, param allowlist, capped fetch_signals (Step 5.4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.registry import (
    READ_TOOL_NAMES,
    WRITE_TOOL_NAMES,
    action_class_for,
    runners_for_ports,
)
from aegis.application.investigation.collect import (
    MemoryCodeSearch,
    MemoryObservabilitySource,
    MemoryRetrieve,
)
from aegis.application.investigation.state import KNOWLEDGE_MAX_CHUNKS, OBS_MAX_ITEMS
from aegis.core.protocols import ObservabilitySignal
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.shared.exceptions import ValidationError
from aegis.tools._limits import KNOWLEDGE_CAP, SIGNAL_CAP
from aegis.tools.fetch_signals import make_fetch_signals


class _UncappedSource:
    """Returns more rows than OBS_MAX_ITEMS so the tool must cap."""

    def fetch_signals(
        self,
        *,
        service: str,
        scenario: str,
        limit: int = 20,
    ) -> list[ObservabilitySignal]:
        now = datetime.now(timezone.utc)
        return [
            ObservabilitySignal(
                kind="log",
                source="simulator",
                timestamp=now,
                service=service,
                summary=f"{scenario} row {index}",
            )
            for index in range(50)
        ]


def _read_runners():
    return runners_for_ports(
        observability=MemoryObservabilitySource(),
        code_search=MemoryCodeSearch(),
        retrieve=MemoryRetrieve(),
    )


def _obs_gateway() -> InvokeTool:
    return InvokeTool(tools=_read_runners())


def test_tool_caps_match_investigation_state() -> None:
    assert SIGNAL_CAP == OBS_MAX_ITEMS
    assert KNOWLEDGE_CAP == KNOWLEDGE_MAX_CHUNKS


def test_registry_lists_only_read_tools() -> None:
    assert WRITE_TOOL_NAMES == frozenset()
    assert READ_TOOL_NAMES == frozenset(
        {"retrieve_knowledge", "fetch_signals", "search_code", "list_deploys"}
    )
    assert "gh_pr_create" not in READ_TOOL_NAMES
    assert "restart_service" not in READ_TOOL_NAMES
    assert "kubectl_delete" not in READ_TOOL_NAMES
    for name in READ_TOOL_NAMES:
        assert action_class_for(name) is ActionClass.READ
    assert action_class_for("mystery") is None
    assert set(_read_runners()) == set(READ_TOOL_NAMES)


def test_unknown_registry_name_is_denied() -> None:
    decision = _obs_gateway().invoke(
        ToolInvokeRequest(
            agent_id="observability",
            tool_name="mystery",
            parameters={"service": "payment"},
            incident_id="11111111-1111-1111-1111-111111111111",
        )
    )
    assert decision.allowed is False
    assert decision.reason == "denied:unknown_tool"
    assert decision.result is None


def test_fetch_signals_with_fake_source_returns_capped_items() -> None:
    runner = make_fetch_signals(_UncappedSource())
    rows = runner({"service": "payment", "scenario": "latency_spike", "limit": 100})
    assert len(rows) == OBS_MAX_ITEMS
    assert all(isinstance(row, dict) for row in rows)
    assert rows[0]["service"] == "payment"
    assert "summary" in rows[0]


def test_extra_parameter_is_rejected() -> None:
    runner = make_fetch_signals(MemoryObservabilitySource())
    with pytest.raises(ValidationError, match="denied:invalid_params"):
        runner({"service": "payment", "url": "http://169.254.169.254/"})

    decision = _obs_gateway().invoke(
        ToolInvokeRequest(
            agent_id="observability",
            tool_name="fetch_signals",
            parameters={"service": "payment", "host": "evil.example"},
            incident_id="11111111-1111-1111-1111-111111111111",
        )
    )
    assert decision.allowed is False
    assert decision.reason == "denied:invalid_params"
    assert decision.result is None
