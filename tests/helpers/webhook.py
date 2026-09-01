"""Sign webhook bodies the same way AEGIS verifies them."""

from __future__ import annotations

import json
from typing import Any

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
