"""``list_deploys`` — recent deploy versions from the code port."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aegis.core.protocols import CodeSearch
from aegis.tools._params import parse_params
from aegis.tools.timeout import run_with_timeout

ToolFn = Callable[[Mapping[str, Any]], Any]


class ListDeploysParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(default="", max_length=255)


def make_list_deploys(search: CodeSearch) -> ToolFn:
    def run(params: Mapping[str, Any]) -> list[dict[str, Any]]:
        body = parse_params(ListDeploysParams, params)

        def _call() -> list[dict[str, Any]]:
            return [_hit_payload(item) for item in search.recent_deploys(service=body.service)]

        return run_with_timeout(_call)

    return run


def _hit_payload(item: object) -> dict[str, Any]:
    return {
        "service": str(getattr(item, "service", "")),
        "version": str(getattr(item, "version", "")),
        "path": str(getattr(item, "path", "")),
        "summary": str(getattr(item, "summary", "")),
    }
