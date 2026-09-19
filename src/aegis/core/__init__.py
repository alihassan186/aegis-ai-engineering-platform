"""Core ports and shared contracts (ADR-001)."""

from aegis.core.protocols import (
    CodeSearch,
    Embedder,
    IncidentFilters,
    IncidentRepository,
    KnowledgeHit,
    KnowledgeStore,
    ObservabilitySource,
)

__all__ = [
    "CodeSearch",
    "Embedder",
    "IncidentFilters",
    "IncidentRepository",
    "KnowledgeHit",
    "KnowledgeStore",
    "ObservabilitySource",
]
