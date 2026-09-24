"""Default notifier: structured log. No SMTP, no phone numbers."""

from __future__ import annotations

import logging

from aegis.core.protocols import NotificationMessage

logger = logging.getLogger("aegis.notifications")


class LogNotifier:
    """CI / local default. Capturable by tests via a FakeNotifier instead."""

    def notify(self, message: NotificationMessage) -> None:
        logger.info(
            "RCA ready for INC-%s" if message.kind == "rca_ready" else "investigation escalated",
            extra={
                "incident_id": message.incident_id,
                "kind": message.kind,
                "event_type": message.event_type,
                "severity": message.severity,
                "service": message.service,
                "reason": message.reason,
                "link": message.link,
                "rca_version": message.rca_version,
            },
        )
