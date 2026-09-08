"""Core ports and shared contracts (ADR-001)."""

from aegis.core.protocols import Embedder, IncidentFilters, IncidentRepository

__all__ = ["Embedder", "IncidentFilters", "IncidentRepository"]
