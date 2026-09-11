"""boto3 clients for LocalStack (endpoint set) or real AWS (endpoint empty)."""

from __future__ import annotations

from typing import Any

from aegis.config.settings import Settings
from aegis.infrastructure.messaging.names import DEFAULT_REGION

# LocalStack dummy IAM. Never used against real AWS (endpoint empty).
_LOCAL_ACCESS_KEY = "test"
_LOCAL_SECRET_KEY = "test"


def messaging_region(settings: Settings) -> str:
    return settings.aws_region.strip() or DEFAULT_REGION


def boto3_client(service: str, settings: Settings) -> Any:
    """events or sqs client. Dummy keys only when AEGIS_AWS_ENDPOINT is set."""
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for EventBridge/SQS messaging.") from exc
    region = messaging_region(settings)
    kwargs: dict[str, Any] = {"region_name": region}
    endpoint = settings.aws_endpoint.strip()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs["aws_access_key_id"] = _LOCAL_ACCESS_KEY
        kwargs["aws_secret_access_key"] = _LOCAL_SECRET_KEY
    return boto3.client(service, **kwargs)
