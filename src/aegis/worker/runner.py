"""No-op specialist runner. Step 4.3 will invoke LangGraph here."""

from __future__ import annotations

import logging

from aegis.domain.events.envelope import DomainEvent

logger = logging.getLogger(__name__)


class LoggingInvestigationRunner:
    def start(self, event: DomainEvent) -> None:
        logger.info(
            "InvestigationRunner stub; specialists not started (Step 4.3)",
            extra={
                "correlation_id": event.correlation_id,
                "incident_id": event.incident_id,
                "event_id": event.event_id,
            },
        )
