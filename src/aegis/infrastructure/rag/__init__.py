"""OpenSearch + embedding adapters (FR-040, FR-043)."""

from aegis.infrastructure.rag.embedder import (
    EMBEDDING_DIMENSION,
    FakeEmbedder,
    TitanEmbedder,
    build_embedder,
)
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore

__all__ = [
    "EMBEDDING_DIMENSION",
    "FakeEmbedder",
    "OpenSearchKnowledgeStore",
    "TitanEmbedder",
    "build_embedder",
]
