"""Ingest orchestrates allowlist → children → embed → store (no OpenSearch)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from aegis.application.rag.allowlist import ALLOWED_RELATIVE_PATHS, repository_root
from aegis.application.rag.chunking import chunk_allowlisted_corpus, retrieval_chunks
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.infrastructure.rag.embedder import EMBEDDING_DIMENSION, FakeEmbedder

RUNBOOK = "docs/knowledge/runbooks/payment-latency-spike.md"


class MemoryKnowledgeStore:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.ensure_calls = 0

    def ensure_hybrid_index(self) -> None:
        self.ensure_calls += 1

    def bulk_upsert(self, documents: Sequence[Mapping[str, Any]]) -> int:
        for document in documents:
            chunk_id = str(document["chunk_id"])
            self.documents[chunk_id] = dict(document)
        return len(documents)

    def count(self) -> int:
        return len(self.documents)

    def search_match(
        self,
        *,
        text: str,
        source_path: str | None = None,
        size: int = 5,
    ) -> list[dict[str, Any]]:
        needle = text.lower()
        hits: list[dict[str, Any]] = []
        for document in self.documents.values():
            if needle not in str(document.get("text", "")).lower():
                continue
            if source_path and document.get("source_path") != source_path:
                continue
            hits.append(document)
            if len(hits) >= size:
                break
        return hits


def test_ingest_indexes_retrieval_children_only() -> None:
    store = MemoryKnowledgeStore()
    result = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
    )
    children = retrieval_chunks(chunk_allowlisted_corpus(repo_root=repository_root()))
    assert result.files == len(ALLOWED_RELATIVE_PATHS) == 24
    assert result.chunks == result.indexed == len(children) == store.count()
    assert result.chunks >= 24
    assert store.ensure_calls == 1
    assert all(doc["role"] == "child" for doc in store.documents.values())
    sample = next(iter(store.documents.values()))
    assert len(sample["embedding"]) == EMBEDDING_DIMENSION
    assert set(sample) >= {
        "text",
        "embedding",
        "source_path",
        "section",
        "doc_type",
        "service",
        "scenario",
        "date",
        "chunk_id",
    }


def test_reingest_overwrites_same_chunk_id() -> None:
    store = MemoryKnowledgeStore()
    first = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
    )
    ids = set(store.documents)
    second = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
    )
    assert first.indexed == second.indexed
    assert set(store.documents) == ids
    assert store.count() == first.chunks


def test_ingest_match_finds_known_source_path() -> None:
    store = MemoryKnowledgeStore()
    ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
    )
    hits = store.search_match(
        text="payment client timeout",
        source_path=RUNBOOK,
        size=5,
    )
    assert hits
    assert all(hit["source_path"] == RUNBOOK for hit in hits)


def test_ingest_fails_if_allowlist_file_missing(tmp_path: Path) -> None:
    store = MemoryKnowledgeStore()
    with pytest.raises(FileNotFoundError, match="allowlist file"):
        ingest_knowledge_corpus(
            embedder=FakeEmbedder(),
            store=store,
            repo_root=tmp_path,
        )
    assert store.ensure_calls == 0
    assert store.count() == 0


def test_cli_requires_opensearch_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AEGIS_OPENSEARCH_URL", raising=False)
    monkeypatch.setenv("AEGIS_SKIP_DOTENV", "1")
    from aegis.rag.ingest import main

    assert main([]) == 1
    assert "AEGIS_OPENSEARCH_URL is required" in capsys.readouterr().err
