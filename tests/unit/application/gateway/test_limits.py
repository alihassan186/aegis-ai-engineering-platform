"""Tool edge hardening: timeout, caps, key allowlist, host allowlist, breaker (Step 5.10)."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from aegis.application.audit.append_audit import AppendAudit
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.limits import (
    CircuitBreaker,
    ToolLimits,
    cap_output,
    harden_tool,
    validate_http_target,
)
from aegis.application.gateway.rate_limit import RateLimiter, ToolRateLimits
from aegis.application.gateway.registry import harden_runners, runners_for_ports
from aegis.application.gateway.untrusted import TRUNCATED_MARKER
from aegis.application.investigation.collect import MemoryCodeSearch, MemoryRetrieve
from aegis.config.settings import DEFAULT_TOOL_ALLOWED_HOSTS, Settings
from aegis.core.protocols import ObservabilitySignal
from aegis.domain.gateway.enums import GatewayVerdict
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.infrastructure.http_safe import open_no_redirect
from aegis.shared.exceptions import ValidationError
from aegis.worker.ports import build_specialist_ports

_INCIDENT = "11111111-1111-1111-1111-111111111111"
_AWS_DUMMY = "AKIA" + "IOSFODNN7EXAMPLE"


def _limits(**overrides: Any) -> ToolLimits:
    base: dict[str, Any] = {
        "timeout_seconds": 0.05,
        "max_output_bytes": 32768,
        "max_param_bytes": 16384,
        "breaker_threshold": 2,
        "breaker_cooldown_seconds": 30.0,
    }
    base.update(overrides)
    return ToolLimits(**base)


def _gateway(
    tools: Mapping[str, Any],
    audit: AppendAudit | None = None,
) -> InvokeTool:
    return InvokeTool(
        tools=tools,
        audit=audit,
        rate_limiter=RateLimiter(
            limits=ToolRateLimits(
                window_seconds=60.0, per_tool_incident=1000, per_agent=1000, fail_closed=False
            )
        ),
    )


def _request(
    tool_name: str = "retrieve_knowledge",
    agent_id: str = "knowledge",
    **parameters: Any,
) -> ToolInvokeRequest:
    return ToolInvokeRequest(
        agent_id=agent_id,
        tool_name=tool_name,
        parameters=parameters,
        incident_id=_INCIDENT,
    )


class _Observability:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_signals(self, *, service: str, scenario: str, limit: int = 20):
        self.calls += 1
        return [
            ObservabilitySignal(
                kind="log",
                source="simulator",
                timestamp=_now(),
                service=service,
                summary="ok",
            )
        ]


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


# ── timeout ──────────────────────────────────────────────────────────────────


def test_sleeping_tool_past_timeout_is_denied_not_hung() -> None:
    audit = AppendAudit()

    def _slow(_params: Mapping[str, Any]) -> str:
        time.sleep(0.4)
        return "late"

    tools = harden_runners({"retrieve_knowledge": _slow}, limits=_limits())
    started = time.monotonic()
    decision = _gateway(tools, audit).invoke(_request(query="latency"))
    elapsed = time.monotonic() - started

    assert decision.allowed is False
    assert decision.reason == "denied:timeout"
    assert elapsed < 0.3
    [entry] = audit.drain()
    assert entry.decision is GatewayVerdict.DENY
    assert entry.reason == "denied:timeout"


# ── output cap ───────────────────────────────────────────────────────────────


def test_string_over_cap_is_truncated_with_marker() -> None:
    capped = cap_output("x" * 5000, max_bytes=200)

    assert isinstance(capped, str)
    assert capped.endswith(TRUNCATED_MARKER)
    assert len(capped.encode("utf-8")) <= 200


def test_list_over_cap_drops_tail_items_and_flags_truncation() -> None:
    rows = [{"summary": "y" * 100} for _ in range(20)]
    tools = harden_runners(
        {"retrieve_knowledge": lambda _p: rows},
        limits=_limits(timeout_seconds=1.0, max_output_bytes=600),
    )
    decision = _gateway(tools).invoke(_request(query="latency"))

    assert decision.allowed is True
    assert 0 < len(decision.result) < len(rows)
    assert decision.envelope is not None
    assert decision.envelope["truncated"] is True
    assert decision.envelope["untrusted"] is True


def test_single_item_larger_than_cap_is_denied() -> None:
    tools = harden_runners(
        {"retrieve_knowledge": lambda _p: [{"summary": "z" * 5000}]},
        limits=_limits(timeout_seconds=1.0, max_output_bytes=200),
    )
    decision = _gateway(tools).invoke(_request(query="latency"))

    assert decision.allowed is False
    assert decision.reason == "denied:output_too_large"


def test_output_is_redacted_before_it_is_cut() -> None:
    """A cut through a secret must not leave a recognizable half key behind."""
    padding = "p" * 80
    text = f"{padding} key={_AWS_DUMMY} tail"
    run = harden_tool(
        "retrieve_knowledge",
        lambda _p: text,
        limits=_limits(timeout_seconds=1.0, max_output_bytes=len(padding) + 12),
        breaker=CircuitBreaker(),
    )

    out = run({})

    assert out.endswith(TRUNCATED_MARKER)
    assert "AKIA" not in out
    assert _AWS_DUMMY[:12] not in out


# ── parameters ───────────────────────────────────────────────────────────────


def test_fetch_signals_with_url_param_is_rejected_and_port_not_called() -> None:
    source = _Observability()
    tools = runners_for_ports(
        observability=source,
        code_search=MemoryCodeSearch(),
        limits=_limits(timeout_seconds=1.0),
    )
    audit = AppendAudit()
    decision = _gateway(tools, audit).invoke(
        _request(
            "fetch_signals",
            agent_id="observability",
            service="payment",
            url="http://169.254.169.254/latest/meta-data/",
        )
    )

    assert decision.allowed is False
    assert decision.reason == "denied:invalid_params"
    assert source.calls == 0
    assert audit.drain()[0].decision is GatewayVerdict.DENY


@pytest.mark.parametrize(
    ("tool", "agent", "params"),
    [
        ("fetch_signals", "observability", {"service": "payment", "extra": 1}),
        ("search_code", "code", {"service": "payment", "path": "/etc/passwd"}),
        ("list_deploys", "code", {"service": "payment", "host": "evil"}),
        ("retrieve_knowledge", "knowledge", {"query": "x", "index": "other"}),
    ],
)
def test_unknown_parameter_key_is_rejected_for_every_tool(
    tool: str, agent: str, params: dict[str, Any]
) -> None:
    tools = runners_for_ports(
        observability=_Observability(),
        code_search=MemoryCodeSearch(),
        retrieve=MemoryRetrieve(),
        limits=_limits(timeout_seconds=1.0),
    )
    decision = _gateway(tools).invoke(_request(tool, agent, **params))

    assert decision.allowed is False
    assert decision.reason == "denied:invalid_params"


def test_oversized_parameters_are_rejected_before_the_tool_runs() -> None:
    ran: list[int] = []

    def _tool(_p: Mapping[str, Any]) -> str:
        ran.append(1)
        return "ok"

    tools = harden_runners({"retrieve_knowledge": _tool}, limits=_limits(max_param_bytes=512))
    decision = _gateway(tools).invoke(_request(query="q" * 10_000))

    assert decision.allowed is False
    assert decision.reason == "denied:payload_too_large"
    assert ran == []


# ── circuit breaker ──────────────────────────────────────────────────────────


def test_breaker_opens_after_consecutive_timeouts_then_denies_without_calling() -> None:
    audit = AppendAudit()
    calls: list[int] = []

    def _hung(_p: Mapping[str, Any]) -> str:
        calls.append(1)
        time.sleep(0.2)
        return "late"

    tools = harden_runners({"retrieve_knowledge": _hung}, limits=_limits(breaker_threshold=2))
    gateway = _gateway(tools, audit)

    first = gateway.invoke(_request(query="a"))
    second = gateway.invoke(_request(query="b"))
    third = gateway.invoke(_request(query="c"))

    assert [first.reason, second.reason] == ["denied:timeout", "denied:timeout"]
    assert third.reason == "denied:dependency_unavailable"
    assert len(calls) == 2
    reasons = [entry.reason for entry in audit.drain()]
    assert reasons[-1] == "denied:dependency_unavailable"


def test_breaker_half_opens_after_cooldown_and_closes_on_success() -> None:
    now = [100.0]
    breaker = CircuitBreaker(threshold=2, cooldown_seconds=30.0, clock=lambda: now[0])

    breaker.record_failure("opensearch")
    assert breaker.allow("opensearch") is True
    breaker.record_failure("opensearch")
    assert breaker.allow("opensearch") is False
    assert breaker.is_open("opensearch") is True

    now[0] += 31.0
    assert breaker.allow("opensearch") is True
    breaker.record_failure("opensearch")
    assert breaker.allow("opensearch") is False

    now[0] += 31.0
    breaker.record_success("opensearch")
    breaker.record_failure("opensearch")
    assert breaker.allow("opensearch") is True


def test_breaker_is_per_dependency() -> None:
    breaker = CircuitBreaker(threshold=1, cooldown_seconds=30.0)
    breaker.record_failure("simulator")

    assert breaker.allow("simulator") is False
    assert breaker.allow("opensearch") is True


def test_dependency_error_becomes_an_audited_deny_not_an_exception() -> None:
    audit = AppendAudit()

    def _down(_p: Mapping[str, Any]) -> str:
        raise ConnectionError("simulator unreachable at http://127.0.0.1:8001")

    tools = harden_runners({"retrieve_knowledge": _down}, limits=_limits(timeout_seconds=1.0))
    decision = _gateway(tools, audit).invoke(_request(query="a"))

    assert decision.allowed is False
    assert decision.reason == "denied:dependency_unavailable"
    [entry] = audit.drain()
    assert entry.reason == "denied:dependency_unavailable"
    assert "127.0.0.1" not in str(entry.output)


def test_invalid_params_do_not_trip_the_breaker() -> None:
    breaker = CircuitBreaker(threshold=1, cooldown_seconds=30.0)

    def _tool(_p: Mapping[str, Any]) -> str:
        raise ValidationError("denied:invalid_params")

    run = harden_tool(
        "retrieve_knowledge", _tool, limits=_limits(timeout_seconds=1.0), breaker=breaker
    )
    with pytest.raises(ValidationError):
        run({})

    assert breaker.allow("opensearch") is True


def test_unexpected_runner_exception_is_still_a_deny_with_audit() -> None:
    audit = AppendAudit()

    def _boom(_p: Mapping[str, Any]) -> str:
        raise RuntimeError("secret internal detail")

    decision = _gateway({"retrieve_knowledge": _boom}, audit).invoke(_request(query="a"))

    assert decision.allowed is False
    assert decision.reason == "denied:tool_error"
    [entry] = audit.drain()
    assert "secret internal detail" not in str(entry.output)


# ── host allowlist + redirects ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8001",
        "http://localhost:9200/",
    ],
)
def test_configured_hosts_are_accepted(url: str) -> None:
    assert validate_http_target(url, allowed_hosts=DEFAULT_TOOL_ALLOWED_HOSTS) == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://127.0.0.1:8001",
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254:8001",
        "http://evil.example.com:8001",
        "http://127.0.0.1:9999",
        "http://user:pw@127.0.0.1:8001",
        "http://",
        "",
    ],
)
def test_unsafe_or_unlisted_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        validate_http_target(url, allowed_hosts=DEFAULT_TOOL_ALLOWED_HOSTS)


def test_worker_refuses_to_build_ports_for_a_metadata_url() -> None:
    settings = Settings(simulator_base_url="http://169.254.169.254")

    with pytest.raises(ValueError):
        build_specialist_ports(settings)


def test_worker_builds_ports_for_the_default_local_urls() -> None:
    ports = build_specialist_ports(Settings())

    assert ports.observability is not None


class _RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(302)
        self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        return


def test_adapter_opener_does_not_follow_redirects() -> None:
    server = HTTPServer(("127.0.0.1", 0), _RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        request = urllib.request.Request(f"http://127.0.0.1:{port}/signals")
        with pytest.raises(urllib.error.HTTPError) as caught:
            open_no_redirect(request, timeout=2.0)
        assert caught.value.code == 302
    finally:
        server.shutdown()
        server.server_close()


# ── settings ─────────────────────────────────────────────────────────────────


def test_limits_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_SKIP_DOTENV", "1")
    monkeypatch.setenv("AEGIS_TOOL_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("AEGIS_TOOL_MAX_OUTPUT_BYTES", "1024")
    monkeypatch.setenv("AEGIS_TOOL_ALLOWED_HOSTS", "10.0.0.5:8001, Sim.internal:8001")

    limits = ToolLimits.from_settings(Settings.from_env())

    assert limits.timeout_seconds == 2.5
    assert limits.max_output_bytes == 1024
    assert limits.allowed_hosts == ("10.0.0.5:8001", "sim.internal:8001")


def test_bad_limit_values_fall_back_to_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_SKIP_DOTENV", "1")
    monkeypatch.setenv("AEGIS_TOOL_TIMEOUT_SECONDS", "-3")
    monkeypatch.setenv("AEGIS_TOOL_MAX_OUTPUT_BYTES", "lots")

    settings = Settings.from_env()

    assert settings.tool_timeout_seconds == 10.0
    assert settings.tool_max_output_bytes == 32768
