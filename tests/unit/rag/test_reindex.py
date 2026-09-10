"""Single-file reindex deletes stale chunks (FR-045). No OpenSearch."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.application.rag.allowlist import repository_root
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.infrastructure.rag.embedder import FakeEmbedder
from tests.unit.rag.test_ingest import RUNBOOK, MemoryKnowledgeStore

OLD_PHRASE = "AEGIS_REINDEX_STALE_PHRASE_ONLY"


def test_single_file_rejects_src() -> None:
    store = MemoryKnowledgeStore()
    with pytest.raises(ValueError, match="allowlist"):
        ingest_knowledge_corpus(
            embedder=FakeEmbedder(),
            store=store,
            repo_root=repository_root(),
            relative_paths=["src/aegis/main.py"],
        )
    assert store.count() == 0


def test_hash_skip_leaves_count_unchanged(tmp_path: Path) -> None:
    store = MemoryKnowledgeStore()
    manifest = tmp_path / "manifest.json"
    first = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
        skip_unchanged=True,
        manifest_path=manifest,
    )
    count = store.count()
    second = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
        skip_unchanged=True,
        manifest_path=manifest,
    )
    assert first.files == 24
    assert first.skipped == 0
    assert second.files == 0
    assert second.skipped == 24
    assert second.indexed == 0
    assert second.deleted == 0
    assert store.count() == count == first.chunks


def test_content_change_drops_stale_chunk_ids() -> None:
    store = MemoryKnowledgeStore()
    ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
        relative_paths=[RUNBOOK],
    )
    store.documents["orphan-old"] = {
        "chunk_id": "orphan-old",
        "source_path": RUNBOOK,
        "text": OLD_PHRASE,
        "section": "gone",
    }
    before = store.count()
    result = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
        relative_paths=[RUNBOOK],
    )
    assert "orphan-old" not in store.documents
    assert OLD_PHRASE not in {doc.get("text") for doc in store.documents.values()}
    assert store.count() == before - 1
    assert result.deleted >= 1
    assert result.files == 1
    assert result.indexed == store.count()
    assert all(doc["source_path"] == RUNBOOK for doc in store.documents.values())
