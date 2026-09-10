"""Allowlist → chunk → embed → bulk index (Step 3.4) and single-file reindex (Step 3.6).

Orchestrates ports only. Domain stays free of OpenSearch and boto3.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegis.application.rag.allowlist import (
    ALLOWED_RELATIVE_PATHS,
    assert_allowlisted,
    iter_allowlisted_paths,
    repository_root,
)
from aegis.application.rag.chunking import chunk_document, retrieval_chunks
from aegis.application.rag.models import Chunk
from aegis.core.protocols import Embedder, KnowledgeStore

EMBED_BATCH_SIZE = 32
MANIFEST_RELATIVE = ".aegis/rag-ingest-manifest.json"


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Counts from one ingest run. ``indexed`` is bulk items written (overwrite-safe)."""

    files: int
    chunks: int
    indexed: int
    skipped: int = 0
    deleted: int = 0


def ingest_knowledge_corpus(
    *,
    embedder: Embedder,
    store: KnowledgeStore,
    repo_root: Path | None = None,
    relative_paths: Sequence[str] | None = None,
    skip_unchanged: bool = False,
    manifest_path: Path | None = None,
) -> IngestResult:
    """Index retrieval children. Optional subset of allowlisted paths (FR-045).

    For each processed file, existing chunks with that ``source_path`` are deleted
    first so heading/text edits cannot leave orphan ``chunk_id``s. Unchanged files
    can be skipped with a content-hash manifest (CLI default).
    """
    root = (repo_root or repository_root()).resolve()
    selected = _resolve_source_paths(root, relative_paths)
    store.ensure_hybrid_index()
    hashes_path = manifest_path or (root / MANIFEST_RELATIVE)
    known_hashes = _load_manifest(hashes_path) if skip_unchanged else {}

    skipped = 0
    deleted = 0
    children: list[Chunk] = []
    processed = 0
    updated_hashes = dict(known_hashes)

    for path in selected:
        rel = assert_allowlisted(path, repo_root=root)
        digest = _file_sha256(path)
        if skip_unchanged and known_hashes.get(rel) == digest:
            skipped += 1
            continue
        deleted += store.delete_by_source_path(rel)
        file_chunks = retrieval_chunks(chunk_document(path, repo_root=root))
        children.extend(file_chunks)
        processed += 1
        updated_hashes[rel] = digest

    if processed == 0 and skipped == 0:
        raise ValueError("RAG ingest produced no retrieval chunks from the selected files.")

    indexed = store.bulk_upsert(_embed_chunks(children, embedder)) if children else 0
    if skip_unchanged:
        _save_manifest(hashes_path, updated_hashes)
    return IngestResult(
        files=processed,
        chunks=len(children),
        indexed=indexed,
        skipped=skipped,
        deleted=deleted,
    )


def _resolve_source_paths(
    repo_root: Path,
    relative_paths: Sequence[str] | None,
) -> tuple[Path, ...]:
    if relative_paths is None:
        return _require_allowlisted_files(repo_root)
    if not relative_paths:
        raise ValueError("relative_paths must be omitted or a non-empty list of allowlisted files.")
    resolved: list[Path] = []
    seen: set[str] = set()
    for raw in relative_paths:
        rel = assert_allowlisted(raw, repo_root=repo_root)
        if rel in seen:
            continue
        seen.add(rel)
        path = repo_root / rel
        if not path.is_file():
            raise FileNotFoundError(
                f"RAG ingest cannot start; allowlist file missing: {path.as_posix()}"
            )
        resolved.append(path)
    return tuple(resolved)


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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    files = raw.get("files", raw)
    if not isinstance(files, dict):
        return {}
    return {str(key): str(value) for key, value in files.items()}


def _save_manifest(path: Path, files: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"version": 1, "files": dict(files)}, indent=2, sort_keys=True) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
