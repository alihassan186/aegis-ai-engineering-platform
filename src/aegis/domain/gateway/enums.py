"""Action classes and verdicts for the tool-use guardrail (FR-052 / FR-067)."""

from enum import StrEnum


class ActionClass(StrEnum):
    """Registry classification. The LLM must never choose this."""

    READ = "read"
    LOW_RISK_WRITE = "low-risk-write"
    HIGH_RISK_WRITE = "high-risk-write"
    DESTRUCTIVE = "destructive"


class GatewayVerdict(StrEnum):
    """Outcome of one invoke. ``pending`` is Phase 8 execute, not v0.6 run."""

    ALLOW = "allow"
    DENY = "deny"
    PENDING = "pending"
