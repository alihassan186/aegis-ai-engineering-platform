"""HTTP client that POSTs incident.signal.v1 to AEGIS (FR-084).

Does not import ``aegis.*``. HMAC format must match ``aegis.api.webhooks.signature``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from apps.simulator.scenarios.catalog import ScenarioId, ScenarioSpec
from apps.simulator.services.catalog import ServiceId

SIGNATURE_HEADER = "X-Aegis-Signature"
WEBHOOK_PATH = "/api/v1/webhooks/incidents"
_PREFIX = "sha256="

_SCENARIO_SEVERITY: Mapping[ScenarioId, str] = {
    ScenarioId.DB_EXHAUSTION: "high",
    ScenarioId.MEMORY_LEAK: "high",
    ScenarioId.LATENCY_SPIKE: "high",
    ScenarioId.BAD_DEPLOYMENT: "critical",
    ScenarioId.QUEUE_BACKLOG: "medium",
    ScenarioId.DEPENDENCY_FAILURE: "high",
}

PostFn = Callable[[str, bytes, dict[str, str]], "WebhookPostResult"]


@dataclass(frozen=True, slots=True)
class WebhookPostResult:
    status_code: int
    body: bytes


class AegisUnreachableError(RuntimeError):
    """AEGIS did not accept a TCP connection."""


def sign_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{_PREFIX}{digest}"


def encode_signal(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def signal_from_scenario(spec: ScenarioSpec) -> dict[str, Any]:
    service: ServiceId = next(iter(spec.statuses))
    return {
        "source": "simulator",
        "service": service.value,
        "title": f"{spec.display_name} on {service.value}",
        "summary": f"{spec.display_name}: synthetic failing signals from {service.value}",
        "severity": _SCENARIO_SEVERITY[spec.id],
        "scenario": spec.id.value,
        "fingerprint": f"{service.value}:{spec.id.value}",
    }


class AegisClient:
    """POST a signed incident signal to AEGIS_BASE_URL."""

    def __init__(
        self,
        *,
        base_url: str,
        secret: str,
        timeout_seconds: float = 5.0,
        post: PostFn | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._timeout_seconds = timeout_seconds
        self._post = post or self._urllib_post

    def emit_incident_signal(self, payload: Mapping[str, Any]) -> WebhookPostResult:
        body = encode_signal(payload)
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign_body(self._secret, body),
        }
        return self._post(f"{self._base_url}{WEBHOOK_PATH}", body, headers)

    def _urllib_post(self, url: str, body: bytes, headers: dict[str, str]) -> WebhookPostResult:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return WebhookPostResult(status_code=int(response.status), body=response.read())
        except urllib.error.HTTPError as exc:
            return WebhookPostResult(status_code=int(exc.code), body=exc.read())
        except urllib.error.URLError as exc:
            reason = exc.reason if exc.reason else exc
            raise AegisUnreachableError(str(reason)) from exc
