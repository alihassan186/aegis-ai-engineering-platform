"""Buffer EventBridge publishes until the request session commits."""

from __future__ import annotations

import logging

from aegis.core.protocols import EventPublisher
from aegis.domain.events.envelope import DomainEvent

logger = logging.getLogger(__name__)


class RequestEventBuffer:
    """``EventPublisher`` that stores events for ``flush_pending_domain_events``."""

    def __init__(self) -> None:
        self.pending: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.pending.append(event)


def flush_pending_domain_events(
    buffer: RequestEventBuffer,
    publisher: EventPublisher | None,
) -> None:
    """Publish after Postgres commit. Fail-soft so create still meets NFR-011."""
    if publisher is None:
        return
    for event in buffer.pending:
        try:
            publisher.publish(event)
        except Exception:
            logger.exception(
                "EventBridge publish failed after commit; investigation may not start",
                extra={
                    "correlation_id": event.correlation_id,
                    "incident_id": event.incident_id,
                    "event_id": event.event_id,
                },
            )
