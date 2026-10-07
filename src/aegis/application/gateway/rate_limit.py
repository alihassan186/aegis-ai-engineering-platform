"""Per-agent and per-tool rate limits (FR-063, RISK-010, THR-014).

Hop cap (MAX_HOPS) stops infinite planning. This stops one node from
hammering retrieve or Bedrock inside a single hop.

Counters live in process memory locally. A process restart resets them.
Production Redis/ElastiCache is Phase 6 — not Postgres row locks per call.
``/health`` is not a tool invoke and is not limited here.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from aegis.config.settings import Settings, get_settings

logger = logging.getLogger("aegis.guardrail")

REASON_RATE_LIMITED = "denied:rate_limited"
REASON_RATE_UNAVAILABLE = "denied:rate_unavailable"


class RateCounter(Protocol):
    """Take one token per key, all-or-nothing. Must not sleep or retry."""

    def try_acquire_all(self, items: Sequence[tuple[str, int, float]]) -> bool: ...


@dataclass(frozen=True, slots=True)
class ToolRateLimits:
    """Env-backed caps. No magic numbers only in the limiter."""

    window_seconds: float
    per_tool_incident: int
    per_agent: int
    fail_closed: bool

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ToolRateLimits:
        cfg = settings or get_settings()
        return cls(
            window_seconds=float(cfg.tool_rate_window_seconds),
            per_tool_incident=cfg.tool_rate_per_tool_incident,
            per_agent=cfg.tool_rate_per_agent,
            fail_closed=cfg.tool_rate_fail_closed,
        )


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class MemoryTokenBucket:
    """In-memory token bucket. Restart empties every bucket (local/CI)."""

    def __init__(self, *, now: Callable[[], float] | None = None) -> None:
        self._now = now or time.monotonic
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def try_acquire_all(self, items: Sequence[tuple[str, int, float]]) -> bool:
        with self._lock:
            moment = self._now()
            next_state: list[tuple[str, _Bucket]] = []
            for key, capacity, window_seconds in items:
                if capacity < 1 or window_seconds <= 0:
                    return False
                refill = capacity / window_seconds
                bucket = self._buckets.get(key)
                if bucket is None:
                    tokens = float(capacity)
                else:
                    elapsed = max(0.0, moment - bucket.updated_at)
                    tokens = min(float(capacity), bucket.tokens + elapsed * refill)
                if tokens < 1.0:
                    return False
                next_state.append((key, _Bucket(tokens=tokens - 1.0, updated_at=moment)))
            for key, bucket in next_state:
                self._buckets[key] = bucket
            return True


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    reason: str


class RateLimiter:
    """Two keys: (agent, tool, incident) and a global per-agent cap.

    One incident cannot starve others (separate incident keys) unless the
    agent has already hit the global cap.
    """

    def __init__(
        self,
        limits: ToolRateLimits | None = None,
        *,
        store: RateCounter | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._limits = limits or ToolRateLimits.from_settings()
        self._store = store or MemoryTokenBucket(now=now)

    @property
    def limits(self) -> ToolRateLimits:
        return self._limits

    def allow(self, *, agent_id: str, tool_name: str, incident_id: str) -> RateLimitDecision:
        incident_key = f"incident:{agent_id}:{tool_name}:{incident_id}"
        agent_key = f"agent:{agent_id}"
        window = self._limits.window_seconds
        try:
            ok = self._store.try_acquire_all(
                (
                    (incident_key, self._limits.per_tool_incident, window),
                    (agent_key, self._limits.per_agent, window),
                )
            )
        except Exception:
            logger.exception("rate-limit store failed")
            if self._limits.fail_closed:
                return RateLimitDecision(allowed=False, reason=REASON_RATE_UNAVAILABLE)
            return RateLimitDecision(allowed=True, reason="allowed:rate_store_skipped")
        if not ok:
            return RateLimitDecision(allowed=False, reason=REASON_RATE_LIMITED)
        return RateLimitDecision(allowed=True, reason="allowed:rate")
