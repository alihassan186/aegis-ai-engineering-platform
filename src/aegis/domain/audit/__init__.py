"""Immutable audit vocabulary. No SQLAlchemy."""

from aegis.domain.audit.entity import GENESIS_HASH, AuditEntry, compute_row_hash

__all__ = [
    "GENESIS_HASH",
    "AuditEntry",
    "compute_row_hash",
]
