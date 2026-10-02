"""``search_code`` — fake/catalog code search. Does not walk ``src/``."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aegis.core.protocols import CodeSearch
from aegis.tools._params import parse_params
from aegis.tools.timeout import run_with_timeout

ToolFn = Callable[[Mapping[str, Any]], Any]


class SearchCodeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(default="", max_length=255)
    scenario: str = Field(default="", max_length=128)


def make_search_code(search: CodeSearch) -> ToolFn:
    def run(params: Mapping[str, Any]) -> list[dict[str, Any]]:
        body = parse_params(SearchCodeParams, params)

        def _call() -> list[dict[str, Any]]:
            return [
                _hit_payload(item)
                for item in search.search(
                    service=body.service,
                    scenario=body.scenario,
                )
            ]

        return run_with_timeout(_call)

    return run


def _hit_payload(item: object) -> dict[str, Any]:
    return {
        "service": str(getattr(item, "service", "")),
        "version": str(getattr(item, "version", "")),
        "path": str(getattr(item, "path", "")),
        "summary": str(getattr(item, "summary", "")),
    }
