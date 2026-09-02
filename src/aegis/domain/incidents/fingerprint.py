"""Stable incident fingerprint for ingest deduplication (FR-007).

v0.3 rule: same ``affected_service`` + scenario + UTC calendar hour
collapse into one **open** incident. Closed incidents do not match
(a new outage after close is a new incident).
"""

from __future__ import annotations

from datetime import datetime, timezone

from aegis.shared.exceptions import ValidationError

UNSPECIFIED_SCENARIO = "unspecified"
_VERSION = "v1"


def compute_fingerprint(
    *,
    affected_service: str,
    scenario: str | None,
    occurred_at: datetime,
) -> str:
    """Return a stable key. Not a cryptographic identity."""
    if occurred_at.tzinfo is None:
        raise ValidationError("occurred_at must be timezone-aware.")
    service = affected_service.strip().lower()
    if not service:
        raise ValidationError("affected_service must not be empty.")
    scenario_key = (scenario or "").strip().lower() or UNSPECIFIED_SCENARIO
    hour = occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
    return f"{_VERSION}|{service}|{scenario_key}|{hour}"
