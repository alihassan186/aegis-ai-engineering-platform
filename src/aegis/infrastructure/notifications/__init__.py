"""Notification adapters. Application depends on ``Notifier``, not these classes."""

from aegis.config.settings import Settings
from aegis.core.protocols import EventPublisher, NotificationMessage, Notifier
from aegis.infrastructure.notifications.log_notifier import LogNotifier
from aegis.infrastructure.notifications.queue_notifier import QueueNotifier


class FanoutNotifier:
    """Log always; queue when EventBridge is configured."""

    def __init__(self, delegates: list[Notifier]) -> None:
        self._delegates = delegates

    def notify(self, message: NotificationMessage) -> None:
        errors: list[Exception] = []
        for delegate in self._delegates:
            try:
                delegate.notify(message)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[0]


def build_notifier(
    settings: Settings | None = None,
    publisher: EventPublisher | None = None,
) -> Notifier:
    log = LogNotifier()
    if publisher is not None:
        return FanoutNotifier([log, QueueNotifier(publisher)])
    _ = settings
    return log


__all__ = ["FanoutNotifier", "LogNotifier", "QueueNotifier", "build_notifier"]
