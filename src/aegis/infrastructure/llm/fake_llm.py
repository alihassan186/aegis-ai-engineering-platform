"""Deterministic LLM for CI and local graph runs. No AWS."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from aegis.application.investigation.rca import estimate_tokens, fixture_rca_payload
from aegis.core.protocols import LlmJsonResult

FAKE_MODEL_ID = "fake-llm"


class FakeLlm:
    """Returns a fixture RCA that cites evidence ids from the DATA block.

    Pass ``responses`` to script invalid-then-valid payloads for retry tests.
    """

    def __init__(self, responses: Sequence[Mapping[str, Any]] | None = None) -> None:
        self._scripted = [dict(item) for item in responses] if responses else []
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    def complete_json(self, *, system: str, user: str) -> LlmJsonResult:
        self.calls += 1
        self.prompts.append((system, user))
        if self._scripted:
            payload = dict(self._scripted.pop(0))
        else:
            payload = fixture_rca_payload(user)
        return LlmJsonResult(
            data=payload,
            model_id=FAKE_MODEL_ID,
            input_tokens=estimate_tokens(system) + estimate_tokens(user),
            output_tokens=estimate_tokens(json.dumps(payload)),
        )
