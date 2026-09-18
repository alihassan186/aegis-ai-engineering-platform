"""Investigation domain types. No FastAPI or SQLAlchemy (ADR-001)."""

from aegis.domain.investigation.enums import EscalateReason

__all__ = ["EscalateReason"]
