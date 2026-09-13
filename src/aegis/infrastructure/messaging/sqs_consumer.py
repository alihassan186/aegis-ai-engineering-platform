"""SQS long-poll loop. Deletes only after the application handler succeeds."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from aegis.config.settings import Settings
from aegis.domain.events.envelope import DomainEvent
from aegis.infrastructure.messaging.names import VISIBILITY_TIMEOUT_SECONDS
from aegis.infrastructure.messaging.sqs import (
    delete_message,
    domain_event_from_sqs_body,
    receive_one,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent], Awaitable[None]]

WORKER_WAIT_SECONDS = 20


class SqsInvestigationConsumer:
    """Long-poll ``investigation-workflow``. No investigation logic here."""

    def __init__(
        self,
        settings: Settings,
        handler: EventHandler,
        *,
        wait_seconds: int = WORKER_WAIT_SECONDS,
        visibility_timeout: int = VISIBILITY_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._handler = handler
        self._wait_seconds = wait_seconds
        self._visibility_timeout = visibility_timeout

    async def poll_once(self) -> bool:
        """Receive at most one message. True if SQS returned something."""
        message = await asyncio.to_thread(
            receive_one,
            self._settings,
            wait_seconds=self._wait_seconds,
            visibility_timeout=self._visibility_timeout,
        )
        if message is None:
            return False
        receipt = str(message["ReceiptHandle"])
        extra: dict[str, str] = {"correlation_id": "-"}
        try:
            event = domain_event_from_sqs_body(str(message["Body"]))
            extra["correlation_id"] = event.correlation_id
            extra["incident_id"] = event.incident_id
            extra["event_id"] = event.event_id
            await self._handler(event)
        except Exception:
            logger.exception(
                "handler failed; leave message for retry/DLQ",
                extra=extra,
            )
            return True
        await asyncio.to_thread(delete_message, self._settings, receipt)
        logger.info("deleted investigation-workflow message", extra=extra)
        return True
