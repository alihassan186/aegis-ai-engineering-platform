"""HTTP client for the production simulator on :8001 (FR-010–012).

Must not import ``apps.simulator`` internals. Source label is ``simulator``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from aegis.core.protocols import ObservabilitySignal

_KIND_MAP = {"log": "log", "metric": "metric", "span": "trace", "trace": "trace"}
_MAX_ITEMS = 20


class SimulatorObservabilityClient:
    """GET ``/signals`` (and one ``/signals/tick`` if the buffer is empty)."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0) -> None:
        url = base_url.strip().rstrip("/")
        if not url:
            raise ValueError("Simulator base URL is required (set AEGIS_SIMULATOR_URL).")
        self._base = url
        self._timeout = timeout_seconds

    def fetch_signals(
        self,
        *,
        service: str,
        scenario: str,
        limit: int = _MAX_ITEMS,
    ) -> list[ObservabilitySignal]:
        cap = max(1, min(limit, _MAX_ITEMS))
        raw = self._list_signals(service=service, limit=cap)
        if not raw:
            self._tick(service)
            raw = self._list_signals(service=service, limit=cap)
        items: list[ObservabilitySignal] = []
        for row in raw:
            mapped = _to_signal(row, fallback_service=service)
            if mapped is not None:
                items.append(mapped)
            if len(items) >= cap:
                break
        return items

    def _list_signals(self, *, service: str, limit: int) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"service": service, "limit": str(max(1, min(limit, 32)))})
        payload = self._request("GET", f"/signals?{query}")
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        return [row for row in items if isinstance(row, dict)]

    def _tick(self, service: str) -> None:
        query = urllib.parse.urlencode({"service": service})
        try:
            self._request("POST", f"/signals/tick?{query}")
        except (ConnectionError, ValueError, urllib.error.HTTPError):
            return

    def _request(self, method: str, path: str) -> dict[str, Any]:
        request = urllib.request.Request(f"{self._base}{path}", method=method)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ConnectionError(f"simulator HTTP {exc.code} for {path}") from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"simulator unreachable at {self._base}") from exc
        if not body.strip():
            return {}
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {}


def _to_signal(row: dict[str, Any], *, fallback_service: str) -> ObservabilitySignal | None:
    raw_kind = str(row.get("kind") or "")
    kind = _KIND_MAP.get(raw_kind)
    if kind is None:
        return None
    timestamp = _parse_timestamp(row.get("timestamp"))
    service = str(row.get("service") or fallback_service)
    return ObservabilitySignal(
        kind=kind,
        source="simulator",
        timestamp=timestamp,
        service=service,
        summary=_summary(kind, row),
    )


def _summary(kind: str, row: dict[str, Any]) -> str:
    if kind == "log":
        severity = row.get("severity") or "info"
        message = row.get("message") or ""
        return f"{severity}: {message}".strip()
    if kind == "metric":
        name = row.get("name") or "metric"
        value = row.get("value")
        unit = row.get("unit") or ""
        return f"{name}={value}{unit}"
    duration = row.get("duration_ms")
    span_id = row.get("span_id") or ""
    return f"span {span_id} duration_ms={duration}"


def _parse_timestamp(raw: object) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw or "").strip()
    if not text:
        return datetime.now(timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
