"""``InvestigationRunner`` that invokes the compiled StateGraph. No Claude."""

from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver

from aegis.application.investigation.collect import SpecialistPorts
from aegis.application.investigation.run import invoke_investigation

logger = logging.getLogger(__name__)


class LangGraphInvestigationRunner:
    """One compiled graph; checkpointer keyed by ``thread_id`` = ``incident_id``."""

    def __init__(
        self,
        checkpointer: InMemorySaver | None = None,
        ports: SpecialistPorts | None = None,
    ) -> None:
        self._checkpointer = checkpointer or InMemorySaver()
        self._ports = ports

    def start(
        self,
        *,
        incident_id: str,
        service: str,
        scenario: str,
        correlation_id: str,
    ) -> None:
        extra = {
            "correlation_id": correlation_id,
            "incident_id": incident_id,
        }
        logger.info(
            "starting investigation graph service=%s scenario=%s thread_id=%s",
            service,
            scenario,
            incident_id,
            extra=extra,
        )
        result = invoke_investigation(
            service=service,
            scenario=scenario,
            incident_id=incident_id,
            thread_id=incident_id,
            checkpointer=self._checkpointer,
            correlation_id=correlation_id,
            ports=self._ports,
        )
        status = result.get("status") or "paused"
        logger.info("investigation graph returned status=%s", status, extra=extra)
