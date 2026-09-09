"""RAG application use cases (Phase 3). No OpenSearch, Bedrock, or HTTP."""

from aegis.application.rag.allowlist import (
    ALLOWED_RELATIVE_PATHS,
    assert_allowlisted,
    is_allowlisted,
    iter_allowlisted_paths,
)
from aegis.application.rag.chunking import (
    chunk_allowlisted_corpus,
    chunk_document,
    parent_chunks,
    retrieval_chunks,
)
from aegis.application.rag.ingest import IngestResult, ingest_knowledge_corpus
from aegis.application.rag.models import Chunk

__all__ = [
    "ALLOWED_RELATIVE_PATHS",
    "Chunk",
    "IngestResult",
    "assert_allowlisted",
    "chunk_allowlisted_corpus",
    "chunk_document",
    "ingest_knowledge_corpus",
    "is_allowlisted",
    "iter_allowlisted_paths",
    "parent_chunks",
    "retrieval_chunks",
]
