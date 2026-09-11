"""Create EventBridge bus, SQS queue, DLQ, and incident.opened.v1 rule."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from aegis.config.settings import Settings
from aegis.core.events import EVENT_SOURCE, INCIDENT_OPENED_V1
from aegis.infrastructure.messaging.clients import boto3_client
from aegis.infrastructure.messaging.names import (
    EVENT_BUS_NAME,
    INVESTIGATION_DLQ_NAME,
    INVESTIGATION_QUEUE_NAME,
    INVESTIGATION_RULE_NAME,
    MAX_RECEIVE_COUNT,
    VISIBILITY_TIMEOUT_SECONDS,
)


@dataclass(frozen=True, slots=True)
class MessagingTopology:
    bus_name: str
    queue_name: str
    dlq_name: str
    queue_url: str
    dlq_url: str
    queue_arn: str


def ensure_investigation_topology(settings: Settings) -> MessagingTopology:
    """Idempotent. Safe to run from docker-up tests and scripts."""
    if not settings.aws_endpoint.strip():
        raise ValueError("AEGIS_AWS_ENDPOINT is required to provision local messaging.")
    events = boto3_client("events", settings)
    sqs = boto3_client("sqs", settings)
    bus = settings.event_bus_name.strip() or EVENT_BUS_NAME
    queue_name = settings.investigation_queue_name.strip() or INVESTIGATION_QUEUE_NAME
    if queue_name != INVESTIGATION_QUEUE_NAME:
        dlq_name = f"{queue_name}-dlq"
    else:
        dlq_name = INVESTIGATION_DLQ_NAME

    _create_event_bus(events, bus)
    dlq_url = _ensure_queue(sqs, dlq_name, attributes={})
    dlq_arn = _queue_arn(sqs, dlq_url)
    redrive = json.dumps(
        {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": str(MAX_RECEIVE_COUNT)}
    )
    queue_url = _ensure_queue(
        sqs,
        queue_name,
        attributes={
            "VisibilityTimeout": str(VISIBILITY_TIMEOUT_SECONDS),
            "RedrivePolicy": redrive,
        },
    )
    queue_arn = _queue_arn(sqs, queue_url)
    _allow_eventbridge(sqs, queue_url, queue_arn)
    _put_opened_rule(events, bus=bus, queue_arn=queue_arn)
    return MessagingTopology(
        bus_name=bus,
        queue_name=queue_name,
        dlq_name=dlq_name,
        queue_url=queue_url,
        dlq_url=dlq_url,
        queue_arn=queue_arn,
    )


def _create_event_bus(events: Any, name: str) -> None:
    try:
        events.create_event_bus(Name=name)
    except Exception as exc:
        if not _already_exists(exc):
            raise


def _ensure_queue(sqs: Any, name: str, *, attributes: dict[str, str]) -> str:
    try:
        if attributes:
            created = sqs.create_queue(QueueName=name, Attributes=attributes)
        else:
            created = sqs.create_queue(QueueName=name)
        url = created["QueueUrl"]
    except Exception as exc:
        if not _already_exists(exc):
            raise
        url = sqs.get_queue_url(QueueName=name)["QueueUrl"]
    if attributes:
        sqs.set_queue_attributes(QueueUrl=url, Attributes=attributes)
    return str(url)


def _queue_arn(sqs: Any, queue_url: str) -> str:
    attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
    return str(attrs["Attributes"]["QueueArn"])


def _allow_eventbridge(sqs: Any, queue_url: str, queue_arn: str) -> None:
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowEventBridgeSend",
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
            }
        ],
    }
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={"Policy": json.dumps(policy)},
    )


def _put_opened_rule(events: Any, *, bus: str, queue_arn: str) -> None:
    pattern = json.dumps({"source": [EVENT_SOURCE], "detail-type": [INCIDENT_OPENED_V1]})
    events.put_rule(
        Name=INVESTIGATION_RULE_NAME,
        EventBusName=bus,
        EventPattern=pattern,
        State="ENABLED",
    )
    events.put_targets(
        EventBusName=bus,
        Rule=INVESTIGATION_RULE_NAME,
        Targets=[{"Id": "investigation-sqs", "Arn": queue_arn}],
    )


def _already_exists(exc: BaseException) -> bool:
    code = ""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str(response.get("Error", {}).get("Code", ""))
    text = f"{code} {exc}".lower()
    exists = {
        "ResourceAlreadyExistsException",
        "QueueAlreadyExists",
        "ResourceConflictException",
    }
    return code in exists or "already exist" in text


def main() -> int:
    settings = Settings.from_env()
    topology = ensure_investigation_topology(settings)
    print(
        "provisioned "
        f"bus={topology.bus_name} queue={topology.queue_name} "
        f"dlq={topology.dlq_name} url={topology.queue_url}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
