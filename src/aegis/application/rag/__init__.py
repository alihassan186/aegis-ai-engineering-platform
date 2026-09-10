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
from aegis.application.rag.eval import (
    EVAL_TOP_K,
    load_eval_cases,
    score_eval_case,
    score_eval_dataset,
)
from aegis.application.rag.ingest import IngestResult, ingest_knowledge_corpus
from aegis.application.rag.models import Chunk
from aegis.application.rag.retrieve import (
    Citation,
    RetrieveFilters,
    RetrieveHit,
    RetrieveKnowledge,
    RetrieveResult,
    merge_hybrid_rankings,
)

__all__ = [
    "ALLOWED_RELATIVE_PATHS",
    "Citation",
    "Chunk",
    "EVAL_TOP_K",
    "IngestResult",
    "RetrieveFilters",
    "RetrieveHit",
    "RetrieveKnowledge",
    "RetrieveResult",
    "assert_allowlisted",
    "chunk_allowlisted_corpus",
    "chunk_document",
    "ingest_knowledge_corpus",
    "is_allowlisted",
    "iter_allowlisted_paths",
    "load_eval_cases",
    "merge_hybrid_rankings",
    "parent_chunks",
    "retrieval_chunks",
    "score_eval_case",
    "score_eval_dataset",
]
