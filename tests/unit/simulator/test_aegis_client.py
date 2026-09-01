"""Simulator HMAC must match AEGIS verification (FR-084, THR-002)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.api.webhooks.signature import compute_signature, verify_signature
from apps.simulator.aegis_client import (
    SIGNATURE_HEADER,
    WEBHOOK_PATH,
    AegisClient,
    WebhookPostResult,
    encode_signal,
    sign_body,
    signal_from_scenario,
)
from apps.simulator.config import Settings
from apps.simulator.main import create_app
from apps.simulator.scenarios import SCENARIOS, ScenarioId
from tests.helpers.auth import TEST_WEBHOOK_SECRET
from tests.helpers.webhook import signal_payload

_SECRET = TEST_WEBHOOK_SECRET


def test_simulator_signature_matches_aegis_verifier() -> None:
    body = encode_signal(signal_payload())

    produced = sign_body(_SECRET, body)
    expected = compute_signature(_SECRET, body)

    assert produced == expected
    assert produced.startswith("sha256=")
    assert verify_signature(_SECRET, body, produced)
    assert not verify_signature("other-secret", body, produced)
    assert not verify_signature(_SECRET, body, None)
    assert not verify_signature(_SECRET, b"tampered", produced)


def test_client_posts_signed_body_to_webhook_path() -> None:
    captured: list[tuple[str, bytes, dict[str, str]]] = []

    def fake_post(url: str, body: bytes, headers: dict[str, str]) -> WebhookPostResult:
        captured.append((url, body, headers))
        return WebhookPostResult(status_code=201, body=b'{"state":"open"}')

    client = AegisClient(
        base_url="http://127.0.0.1:8000/",
        secret=_SECRET,
        post=fake_post,
    )
    payload = signal_from_scenario(SCENARIOS[ScenarioId.LATENCY_SPIKE])
    result = client.emit_incident_signal(payload)

    assert result.status_code == 201
    assert len(captured) == 1
    url, body, headers = captured[0]
    assert url == f"http://127.0.0.1:8000{WEBHOOK_PATH}"
    assert headers["Content-Type"] == "application/json"
    assert headers[SIGNATURE_HEADER] == sign_body(_SECRET, body)
    assert verify_signature(_SECRET, body, headers[SIGNATURE_HEADER])
    assert payload["service"] == "payment"
    assert payload["scenario"] == "latency_spike"
    assert payload["severity"] == "high"


def test_emit_requires_an_active_scenario() -> None:
    application = create_app(
        Settings(
            environment="test",
            aegis_base_url="http://127.0.0.1:8000",
            webhook_secret=_SECRET,
        )
    )
    with TestClient(application) as client:
        response = client.post("/emit")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_ACTIVE_SCENARIO"


def test_emit_posts_active_scenario_signal() -> None:
    captured: list[tuple[str, bytes, dict[str, str]]] = []

    def fake_post(url: str, body: bytes, headers: dict[str, str]) -> WebhookPostResult:
        captured.append((url, body, headers))
        return WebhookPostResult(
            status_code=201,
            body=b'{"id":"11111111-1111-1111-1111-111111111111","state":"open"}',
        )

    application = create_app(
        Settings(
            environment="test",
            aegis_base_url="http://127.0.0.1:8000",
            webhook_secret=_SECRET,
        )
    )
    with TestClient(application) as client:
        application.state.aegis_client = AegisClient(
            base_url="http://127.0.0.1:8000",
            secret=_SECRET,
            post=fake_post,
        )
        client.post("/scenarios/latency_spike")
        response = client.post("/emit")

    assert response.status_code == 201
    assert response.json()["state"] == "open"
    assert len(captured) == 1
    assert verify_signature(_SECRET, captured[0][1], captured[0][2][SIGNATURE_HEADER])
