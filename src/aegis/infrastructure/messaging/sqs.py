"""SQS receive/delete for tests and (later) the worker. No investigation logic."""

from __future__ import annotations

import json
import time
from typing import Any

from aegis.config.settings import Settings
from aegis.core.events import DomainEvent
from aegis.infrastructure.messaging.clients import boto3_client
from aegis.infrastructure.messaging.names import INVESTIGATION_QUEUE_NAME


def queue_url(settings: Settings, *, sqs: Any | None = None) -> str:
    client = sqs if sqs is not None else boto3_client("sqs", settings)
    name = settings.investigation_queue_name.strip() or INVESTIGATION_QUEUE_NAME
    return str(client.get_queue_url(QueueName=name)["QueueUrl"])


def receive_one(
    settings: Settings,
    *,
    wait_seconds: int = 8,
    visibility_timeout: int = 30,
    sqs: Any | None = None,
) -> dict[str, Any] | None:
    client = sqs if sqs is not None else boto3_client("sqs", settings)
    url = queue_url(settings, sqs=client)
    deadline = time.monotonic() + max(1, wait_seconds)
    while time.monotonic() < deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        response = client.receive_message(
            QueueUrl=url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=min(20, remaining),
            VisibilityTimeout=visibility_timeout,
        )
        messages = response.get("Messages") or []
        if messages:
            return dict(messages[0])
    return None


def delete_message(settings: Settings, receipt_handle: str, *, sqs: Any | None = None) -> None:
    client = sqs if sqs is not None else boto3_client("sqs", settings)
    url = queue_url(settings, sqs=client)
    client.delete_message(QueueUrl=url, ReceiptHandle=receipt_handle)


def domain_event_from_sqs_body(body: str) -> DomainEvent:
    """EventBridge wraps our Detail inside the SQS message body."""
    payload = json.loads(body)
    detail = payload.get("detail", payload)
    if isinstance(detail, str):
        detail = json.loads(detail)
    if not isinstance(detail, dict):
        raise ValueError("SQS body is not an EventBridge detail object.")
    return DomainEvent(
        event_id=str(detail["event_id"]),
        event_type=str(detail["event_type"]),
        schema_version=str(detail["schema_version"]),
        timestamp=str(detail["timestamp"]),
        correlation_id=str(detail["correlation_id"]),
        incident_id=str(detail["incident_id"]),
    )
