"""Dummy-secret tests for DLP-lite redaction (FR-019). No real keys."""

from __future__ import annotations

import pytest

from aegis.application.security.redact import redact, redact_for_llm, redact_mapping

# Documented fakes only — never paste live credentials into the repo.
_AWS = "AKIAIOSFODNN7EXAMPLE"
_AWS_TEMP = "ASIAIOSFODNN7EXAMPLE"
_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBFAKEPRIVATEKEYNOTREAL0000000000000000000000000000\n"
    "-----END PRIVATE KEY-----"
)
_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJkdW1teS11c2VyIn0."
    "dummy_signature_not_a_real_secret"
)
_PG = "postgresql+asyncpg://dummy:dummy-pass-NOT-REAL@127.0.0.1:5434/aegis"
_PG_PLAIN = "postgres://dummy:dummy-pass-NOT-REAL@db.internal:5432/app"
_BEARER = "Bearer dummy-token-NOT-REAL"
# Shaped for our regex, not for GitHub/Slack push-protection scanners.
_SLACK = "xoxb-DUMMYNOTAREALSLACKTOKEN"
_GITHUB = "ghp_dummyNotARealGitHubPatToken"
_EMAIL = "sre-dummy@example.com"


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        (f"access_key={_AWS}", "aws_access_key"),
        (f"sts={_AWS_TEMP}", "aws_access_key"),
        (f"pem\n{_PEM}\nend", "private_key"),
        (f"auth {_JWT}", "jwt"),
        (f"url {_PG}", "database_url"),
        (f"url {_PG_PLAIN}", "database_url"),
        (f"header {_BEARER}", "bearer_token"),
        (f"slack {_SLACK}", "slack_token"),
        (f"pat {_GITHUB}", "github_pat"),
        (f"page {_EMAIL}", "email"),
    ],
)
def test_each_pattern_removes_dummy_secret(raw: str, kind: str) -> None:
    result = redact(raw)

    assert result.count >= 1
    assert kind in result.kinds
    assert _AWS not in result.text
    assert _AWS_TEMP not in result.text
    assert "dummy-pass-NOT-REAL" not in result.text
    assert "dummy-token-NOT-REAL" not in result.text
    assert _JWT not in result.text
    assert "BEGIN PRIVATE KEY" not in result.text
    assert _SLACK not in result.text
    assert _GITHUB not in result.text
    assert _EMAIL not in result.text
    assert f"[REDACTED:{kind}]" in result.text


def test_redact_is_idempotent() -> None:
    mixed = f"key={_AWS} token={_JWT} db={_PG}"
    first = redact(mixed)
    second = redact(first.text)

    assert first.text == second.text
    assert second.count == 0
    assert first.count == 3


def test_clean_text_is_unchanged() -> None:
    text = "p99 latency 1.8s on payment checkout"
    result = redact(text)

    assert result.text == text
    assert result.count == 0
    assert result.kinds == ()


def test_empty_text_is_a_noop() -> None:
    assert redact("").text == ""
    assert redact("").count == 0


def test_redact_for_llm_matches_redact_text() -> None:
    raw = f"log line key={_AWS}"
    assert redact_for_llm(raw) == redact(raw).text
    assert _AWS not in redact_for_llm(raw)


def test_redact_mapping_walks_nested_strings() -> None:
    payload, count = redact_mapping(
        {
            "query": f"connect {_PG}",
            "citation": {"document": "docs/knowledge/runbooks/payment-latency-spike.md"},
            "nested": [_EMAIL],
        }
    )

    assert count >= 2
    assert "dummy-pass-NOT-REAL" not in str(payload)
    assert _EMAIL not in str(payload)
    assert payload["citation"]["document"].endswith("payment-latency-spike.md")
