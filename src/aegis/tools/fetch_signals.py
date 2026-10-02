"""``fetch_signals`` — simulator / fake observability behind the gateway."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aegis.core.protocols import ObservabilitySource
from aegis.tools._limits import SIGNAL_CAP
from aegis.tools._params import parse_params
from aegis.tools.timeout import run_with_timeout

ToolFn = Callable[[Mapping[str, Any]], Any]


class FetchSignalsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(default="", max_length=255)
    scenario: str = Field(default="", max_length=128)
    limit: int = Field(default=SIGNAL_CAP, ge=1)


def make_fetch_signals(source: ObservabilitySource) -> ToolFn:
    def run(params: Mapping[str, Any]) -> list[dict[str, Any]]:
        body = parse_params(FetchSignalsParams, params)
        cap = min(int(body.limit), SIGNAL_CAP)

        def _call() -> list[dict[str, Any]]:
            signals = source.fetch_signals(
                service=body.service,
                scenario=body.scenario,
                limit=cap,
            )
            return [_signal_payload(item) for item in list(signals)[:cap]]

        return run_with_timeout(_call)

    return run


def _signal_payload(item: object) -> dict[str, Any]:
    timestamp = getattr(item, "timestamp", "")
    if hasattr(timestamp, "isoformat"):
        timestamp = timestamp.isoformat()
    return {
        "kind": str(getattr(item, "kind", "")),
        "source": str(getattr(item, "source", "")),
        "timestamp": str(timestamp),
        "service": str(getattr(item, "service", "")),
        "summary": str(getattr(item, "summary", "")),
    }
