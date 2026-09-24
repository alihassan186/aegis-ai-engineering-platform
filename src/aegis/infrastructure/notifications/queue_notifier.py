"""Optional EventBridge publish onto the notification queue (ADR-003).

Does not create a rag-indexing consumer. Slow Slack/email must not sit
on the investigation-workflow visibility timeout.
"""

from __future__ import annotations

from aegis.core.events import rca_completed_v1, rca_escalated_v1
from aegis.core.protocols import EventPublisher, NotificationMessage


class QueueNotifier:
    """Puts ``rca.completed.v1`` / ``rca.escalated.v1`` on ``aegis-events``."""

    def __init__(self, publisher: EventPublisher) -> None:
        self._publisher = publisher

    def notify(self, message: NotificationMessage) -> None:
        if message.event_type == "rca.escalated.v1":
            event = rca_escalated_v1(incident_id=message.incident_id)
        else:
            event = rca_completed_v1(incident_id=message.incident_id)
        self._publisher.publish(event)
