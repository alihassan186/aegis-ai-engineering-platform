"""Composition root for ``uv run python -m aegis.worker`` (NFR-006)."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis.application.investigation.consume_opened import ConsumeOpenedIncident
from aegis.config.settings import Settings, get_settings
from aegis.domain.events.envelope import DomainEvent
from aegis.infrastructure.database.session import start_database, stop_database
from aegis.infrastructure.messaging.sqs_consumer import SqsInvestigationConsumer
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository
from aegis.infrastructure.repositories.processed_event_store import SqlAlchemyProcessedEventStore
from aegis.worker.runner import LoggingInvestigationRunner

logger = logging.getLogger("aegis.worker")


class _CorrelationFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return super().format(record)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _CorrelationFormatter(
            "%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def main() -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)
    if not settings.database_url:
        raise SystemExit("AEGIS_DATABASE_URL is required for the investigation worker.")
    if not settings.aws_endpoint.strip():
        raise SystemExit("AEGIS_AWS_ENDPOINT is required for the investigation worker.")
    try:
        asyncio.run(run_worker(settings))
    except KeyboardInterrupt:
        logger.info("worker interrupted")


async def run_worker(settings: Settings) -> None:
    engine, session_factory = await start_database(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            signal.signal(sig, lambda _s, _f: stop.set())

    runner = LoggingInvestigationRunner()

    async def handle(event: DomainEvent) -> None:
        await _handle_opened(session_factory, event, runner)

    consumer = SqsInvestigationConsumer(settings, handle)
    logger.info(
        "worker polling %s",
        settings.investigation_queue_name,
        extra={"correlation_id": "-"},
    )
    try:
        while not stop.is_set():
            await consumer.poll_once()
        logger.info("shutdown: finished current poll cycle")
    finally:
        await stop_database(engine)


async def _handle_opened(
    session_factory: async_sessionmaker[AsyncSession],
    event: DomainEvent,
    runner: LoggingInvestigationRunner,
) -> None:
    session = session_factory()
    try:
        consume = ConsumeOpenedIncident(
            SqlAlchemyIncidentRepository(session),
            SqlAlchemyProcessedEventStore(session),
            runner=runner,
        )
        await consume.execute(event)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


if __name__ == "__main__":
    main()
