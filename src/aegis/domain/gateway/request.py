"""Inbound guardrail contract. ``action_class`` on the request is untrusted."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aegis.shared.exceptions import ValidationError


class ToolInvokeRequest:
    """What a node presents to ``ToolGateway.invoke``."""

    def __init__(
        self,
        *,
        agent_id: str,
        tool_name: str,
        parameters: Mapping[str, Any],
        incident_id: str,
        action_class: str | None = None,
    ) -> None:
        self._agent_id = agent_id.strip()
        self._tool_name = tool_name.strip()
        if not self._tool_name:
            raise ValidationError("tool_name must not be empty.")
        if not self._agent_id:
            raise ValidationError("agent_id must not be empty.")
        if not incident_id.strip():
            raise ValidationError("incident_id must not be empty.")
        self._parameters = dict(parameters)
        self._incident_id = incident_id.strip()
        # Stored only so tests can prove we ignore a caller-supplied class.
        self._claimed_action_class = (action_class or "").strip() or None

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def parameters(self) -> dict[str, Any]:
        return dict(self._parameters)

    @property
    def incident_id(self) -> str:
        return self._incident_id

    @property
    def claimed_action_class(self) -> str | None:
        """Value from the caller / model. Guardrail must not trust it."""
        return self._claimed_action_class
