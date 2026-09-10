"""Allowlist → chunk → embed → bulk index (Step 3.4).

Orchestrates ports only. Domain stays free of OpenSearch and boto3.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegis.application.rag.allowlist import (
    ALLOWED_RELATIVE_PATHS,
    iter_allowlisted_paths,
    repository_root,
)
from aegis.application.rag.chunking import chunk_allowlisted_corpus, retrieval_chunks
from aegis.application.rag.models import Chunk
from aegis.core.protocols import Embedder, KnowledgeStore

EMBED_BATCH_SIZE = 32


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Counts from one ingest run. ``indexed`` is bulk items written (overwrite-safe)."""

    files: int
    chunks: int
    indexed: int


def ingest_knowledge_corpus(
    *,
    embedder: Embedder,
    store: KnowledgeStore,
    repo_root: Path | None = None,
) -> IngestResult:
    """Index retrieval children from the 24 allowlisted files. Missing file → fail."""
    root = (repo_root or repository_root()).resolve()
    paths = _require_allowlisted_files(root)
    store.ensure_hybrid_index()
    children = retrieval_chunks(chunk_allowlisted_corpus(repo_root=root))
    if not children:
        raise ValueError("RAG ingest produced no retrieval chunks from the allowlist.")
    documents = _embed_chunks(children, embedder)
    indexed = store.bulk_upsert(documents)
    return IngestResult(files=len(paths), chunks=len(children), indexed=indexed)


def _require_allowlisted_files(repo_root: Path) -> tuple[Path, ...]:
    paths = iter_allowlisted_paths(repo_root=repo_root)
    missing = [path.as_posix() for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "RAG ingest cannot start; allowlist file(s) missing: " + ", ".join(missing)
        )
    expected = len(ALLOWED_RELATIVE_PATHS)
    if len(paths) != expected:
        raise FileNotFoundError(
            f"RAG ingest expected {expected} allowlisted files, found {len(paths)}."
        )
    return paths


def _embed_chunks(chunks: Sequence[Chunk], embedder: Embedder) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for offset in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[offset : offset + EMBED_BATCH_SIZE]
        vectors = embedder.embed_texts([chunk.text for chunk in batch])
        if len(vectors) != len(batch):
            raise ValueError("embed_texts returned a different number of vectors than texts.")
        for chunk, vector in zip(batch, vectors, strict=True):
            documents.append(_document_from_chunk(chunk, vector))
    return documents


def _document_from_chunk(chunk: Chunk, embedding: Sequence[float]) -> dict[str, Any]:
    meta: Mapping[str, str] = chunk.metadata
    return {
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "embedding": [float(value) for value in embedding],
        "source_path": chunk.source_path,
        "section": chunk.section,
        "doc_type": meta.get("doc_type", ""),
        "service": meta.get("service", ""),
        "scenario": meta.get("scenario", ""),
        "date": meta.get("date", ""),
        "incident_id": meta.get("incident_id", ""),
        "role": meta.get("role", "child"),
        "parent_id": meta.get("parent_id", ""),
    }
