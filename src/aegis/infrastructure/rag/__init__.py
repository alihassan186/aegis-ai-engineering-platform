"""OpenSearch + embedding adapters (FR-040). Ingest write is Step 3.4."""

from aegis.infrastructure.rag.embedder import (
    EMBEDDING_DIMENSION,
    FakeEmbedder,
    TitanEmbedder,
    build_embedder,
)

__all__ = [
    "EMBEDDING_DIMENSION",
    "FakeEmbedder",
    "TitanEmbedder",
    "build_embedder",
]
