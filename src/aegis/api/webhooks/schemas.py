"""Inbound incident.signal.v1 body (FR-113). Maps onto CreateIncident fields."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from aegis.domain.incidents.enums import Severity


class IncidentSignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=64)
    service: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=512)
    severity: Severity
    summary: str | None = Field(default=None, max_length=2048)
    scenario: str | None = Field(default=None, max_length=64)
    fingerprint: str | None = Field(default=None, max_length=128)
