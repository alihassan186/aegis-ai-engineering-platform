"""After-commit EventBridge flush is fail-soft (NFR-011)."""

from __future__ import annotations

from aegis.api.event_publish import RequestEventBuffer, flush_pending_domain_events
from aegis.domain.events.envelope import incident_opened_v1


class _ExplodingPublisher:
    def publish(self, event: object) -> None:
        raise ConnectionError("bus down")


def test_flush_swallows_publish_errors() -> None:
    buffer = RequestEventBuffer()
    buffer.publish(incident_opened_v1(incident_id="i", correlation_id="c"))
    flush_pending_domain_events(buffer, _ExplodingPublisher())


def test_flush_skips_when_messaging_unset() -> None:
    buffer = RequestEventBuffer()
    buffer.publish(incident_opened_v1(incident_id="i", correlation_id="c"))
    flush_pending_domain_events(buffer, None)
