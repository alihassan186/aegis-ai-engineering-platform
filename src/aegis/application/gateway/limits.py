"""Tool edge hardening (Step 5.10, NFR-011): size, time, host, and dependency health.

Policy answers *may I*. This module answers *how long, how large, to where, and is
the dependency healthy*. ``registry.runners_for_ports`` wraps every callable here,
so no specialist node and no MCP client can skip it.

Choices (each has a test):

* Unknown or oversized parameters are rejected before the tool runs.
* Output is redacted, then **truncated** with ``[truncated]`` (strings) or by
  dropping tail items (lists). If not even one item fits, the call is denied.
* Timeouts, dependency errors, and an open breaker all become a deny
  (``denied:timeout`` / ``denied:dependency_unavailable``), which the gateway audits.
* The circuit breaker is in-process, like 5.7's counters. A restart resets it.
  Shared state (Redis) is a Phase 6 note, not built here.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import threading
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from aegis.application.gateway.untrusted import TRUNCATED_MARKER, redact_result
from aegis.config.settings import DEFAULT_TOOL_ALLOWED_HOSTS, Settings, get_settings
from aegis.shared.exceptions import ValidationError
from aegis.tools.timeout import run_with_timeout

logger = logging.getLogger("aegis.guardrail")

ToolFn = Callable[[Mapping[str, Any]], Any]
Clock = Callable[[], float]

DENY_TIMEOUT = "denied:timeout"
DENY_INVALID_PARAMS = "denied:invalid_params"
DENY_PAYLOAD_TOO_LARGE = "denied:payload_too_large"
DENY_OUTPUT_TOO_LARGE = "denied:output_too_large"
DENY_DEPENDENCY = "denied:dependency_unavailable"

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True, slots=True)
class ToolLimits:
    timeout_seconds: float = 10.0
    max_output_bytes: int = 32768
    max_param_bytes: int = 16384
    breaker_threshold: int = 3
    breaker_cooldown_seconds: float = 30.0
    allowed_hosts: tuple[str, ...] = DEFAULT_TOOL_ALLOWED_HOSTS

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ToolLimits:
        resolved = settings or get_settings()
        return cls(
            timeout_seconds=resolved.tool_timeout_seconds,
            max_output_bytes=resolved.tool_max_output_bytes,
            max_param_bytes=resolved.tool_max_param_bytes,
            breaker_threshold=resolved.tool_breaker_threshold,
            breaker_cooldown_seconds=resolved.tool_breaker_cooldown_seconds,
            allowed_hosts=resolved.tool_allowed_hosts,
        )


class CappedList(list):
    """A list that lost tail items to the output cap. Survives until redaction."""

    truncated: bool = True


@dataclass(slots=True)
class _BreakerState:
    failures: int = 0
    opened_until: float = 0.0


@dataclass
class CircuitBreaker:
    """N consecutive failures open the circuit for ``cooldown_seconds``.

    After the cooldown calls are allowed again. A single failure then re-opens it,
    a success closes it. Keyed by dependency (``simulator``, ``opensearch``).
    """

    threshold: int = 3
    cooldown_seconds: float = 30.0
    clock: Clock = time.monotonic
    _states: dict[str, _BreakerState] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self, key: str) -> bool:
        with self._lock:
            state = self._states.get(key)
            if state is None or state.failures < self.threshold:
                return True
            return self.clock() >= state.opened_until

    def record_success(self, key: str) -> None:
        with self._lock:
            self._states.pop(key, None)

    def record_failure(self, key: str) -> None:
        with self._lock:
            state = self._states.setdefault(key, _BreakerState())
            state.failures += 1
            if state.failures >= self.threshold:
                state.opened_until = self.clock() + self.cooldown_seconds

    def is_open(self, key: str) -> bool:
        return not self.allow(key)


TOOL_DEPENDENCY: Mapping[str, str] = {
    "fetch_signals": "simulator",
    "retrieve_knowledge": "opensearch",
    "search_code": "code",
    "list_deploys": "code",
}


def harden_tool(
    tool_name: str,
    fn: ToolFn,
    *,
    limits: ToolLimits,
    breaker: CircuitBreaker,
    allowed_params: Collection[str] | None = None,
    dependency: str | None = None,
) -> ToolFn:
    """Wrap one runner. Raises ``ValidationError('denied:...')`` so the gateway audits it."""
    key = dependency or TOOL_DEPENDENCY.get(tool_name, tool_name)
    allowed = None if allowed_params is None else frozenset(allowed_params)

    def run(params: Mapping[str, Any]) -> Any:
        _check_params(params, allowed=allowed, max_bytes=limits.max_param_bytes)
        if not breaker.allow(key):
            raise ValidationError(DENY_DEPENDENCY)
        try:
            raw = run_with_timeout(lambda: fn(params), seconds=limits.timeout_seconds)
        except ValidationError as exc:
            if str(exc) == DENY_TIMEOUT:
                breaker.record_failure(key)
            raise
        except Exception as exc:
            breaker.record_failure(key)
            logger.warning(
                "tool dependency error tool=%s dependency=%s error=%s",
                tool_name,
                key,
                type(exc).__name__,
            )
            raise ValidationError(DENY_DEPENDENCY) from exc
        breaker.record_success(key)
        return cap_output(redact_result(raw), max_bytes=limits.max_output_bytes)

    return run


def cap_output(value: Any, *, max_bytes: int) -> Any:
    """Truncate with a marker (strings) or drop tail items (lists). Else deny."""
    if _size(value) <= max_bytes:
        return value
    if isinstance(value, str):
        return _truncate_text(value, max_bytes)
    if isinstance(value, list):
        kept: list[Any] = []
        for item in value:
            if _size([*kept, item]) > max_bytes:
                break
            kept.append(item)
        if not kept:
            raise ValidationError(DENY_OUTPUT_TOO_LARGE)
        capped = CappedList(kept)
        return capped
    raise ValidationError(DENY_OUTPUT_TOO_LARGE)


def validate_http_target(url: str, *, allowed_hosts: Collection[str]) -> str:
    """Config-time SSRF check for an adapter base URL. Returns the normalized URL.

    Only ``http``/``https``, no credentials, no link-local or metadata addresses,
    and ``host:port`` must be in the allowlist. Never called with user input.
    """
    text = (url or "").strip()
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"tool URL scheme '{scheme or '?'}' is not allowed (http/https only).")
    host = (parts.hostname or "").lower()
    if not host:
        raise ValueError("tool URL has no host.")
    if parts.username or parts.password:
        raise ValueError("tool URL must not embed credentials.")
    if _is_blocked_address(host):
        raise ValueError(f"tool URL host '{host}' is link-local or otherwise blocked.")
    port = parts.port or _DEFAULT_PORTS[scheme]
    authority = f"{host}:{port}"
    allowed = {entry.strip().lower() for entry in allowed_hosts}
    if authority not in allowed:
        raise ValueError(f"tool URL host '{authority}' is not in AEGIS_TOOL_ALLOWED_HOSTS.")
    return text.rstrip("/")


def _check_params(
    params: Mapping[str, Any],
    *,
    allowed: frozenset[str] | None,
    max_bytes: int,
) -> None:
    if allowed is not None:
        unknown = set(params) - allowed
        if unknown:
            raise ValidationError(DENY_INVALID_PARAMS)
    if _size(dict(params)) > max_bytes:
        raise ValidationError(DENY_PAYLOAD_TOO_LARGE)


def _size(value: Any) -> int:
    return len(json.dumps(value, default=str, separators=(",", ":")).encode("utf-8"))


def _truncate_text(text: str, max_bytes: int) -> str:
    budget = max(0, max_bytes - len(TRUNCATED_MARKER.encode("utf-8")))
    cut = text.encode("utf-8")[:budget].decode("utf-8", errors="ignore")
    return cut + TRUNCATED_MARKER


def _is_blocked_address(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )
