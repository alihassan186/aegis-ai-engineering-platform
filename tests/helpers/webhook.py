"""Sign webhook bodies the same way AEGIS verifies them."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from aegis.api.webhooks.signature import SIGNATURE_HEADER, compute_signature
from tests.helpers.auth import TEST_WEBHOOK_SECRET


def signal_payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "source": "simulator",
        "service": "payment",
        "title": "Latency spike on payment",
        "summary": "Latency spike: synthetic failing signals from payment",
        "severity": "high",
        "scenario": "latency_spike",
        "fingerprint": "payment:latency_spike",
    }
    body.update(overrides)
    return body


def isolated_signal_payload(**overrides: Any) -> dict[str, Any]:
    """Payload whose fingerprint will not match leftover open incidents.

    Ingest collapses ``service + scenario + UTC hour``. The v0.3 demo commits
    ``payment`` / ``latency_spike`` into the shared local database, so tests
    that expect HTTP 201 must not reuse that pair.
    """
    token = uuid4().hex[:8]
    service = str(overrides.pop("service", f"payment-{token}"))
    scenario = str(overrides.pop("scenario", f"latency_spike-{token}"))
    return signal_payload(
        service=service,
        scenario=scenario,
        title=overrides.pop("title", f"Latency spike on {service}"),
        summary=overrides.pop("summary", f"Latency spike: synthetic failing signals from {service}"),
        fingerprint=overrides.pop("fingerprint", f"{service}:{scenario}"),
        **overrides,
    )


def encode_signal(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def signed_webhook_headers(
    body: bytes,
    *,
    secret: str = TEST_WEBHOOK_SECRET,
) -> dict[str, str]:
    return {
        SIGNATURE_HEADER: compute_signature(secret, body),
        "Content-Type": "application/json",
    }
