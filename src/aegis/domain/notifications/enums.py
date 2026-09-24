"""Notification kinds (FR-027, FR-028). Not email/SMS channels."""

from enum import StrEnum


class NotificationKind(StrEnum):
    RCA_READY = "rca_ready"
    ESCALATION = "escalation"
