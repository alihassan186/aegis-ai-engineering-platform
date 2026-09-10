"""Live reindex: edit an allowlisted file, retrieve the new phrase (FR-045)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aegis.application.rag.allowlist import repository_root
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.application.rag.retrieve import RetrieveKnowledge
from aegis.infrastructure.rag.embedder import FakeEmbedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore

RUNBOOK = "docs/knowledge/runbooks/payment-latency-spike.md"
PROBE = "AEGIS_REINDEX_PROBE_3_6_UNIQUE"
PROBE_BLOCK = f"\n\n## Reindex probe\n\n{PROBE}\n"


@pytest.fixture
def opensearch_url() -> str:
    url = os.getenv("AEGIS_OPENSEARCH_URL", "").strip().rstrip("/")
    if not url:
        pytest.skip("AEGIS_OPENSEARCH_URL is unset; OpenSearch is optional for this suite.")
    return url


@pytest.fixture
def store(opensearch_url: str) -> OpenSearchKnowledgeStore:
    return OpenSearchKnowledgeStore(opensearch_url)


def _retrieve(store: OpenSearchKnowledgeStore) -> RetrieveKnowledge:
    return RetrieveKnowledge(embedder=FakeEmbedder(), store=store)


def test_single_file_reindex_updates_retrieve(store: OpenSearchKnowledgeStore) -> None:
    root = repository_root()
    path = root / RUNBOOK
    original = path.read_text(encoding="utf-8")
    embedder = FakeEmbedder()
    try:
        baseline = ingest_knowledge_corpus(
            embedder=embedder,
            store=store,
            repo_root=root,
            skip_unchanged=False,
        )
        count_before = store.count()
        assert count_before == baseline.chunks

        path.write_text(original + PROBE_BLOCK, encoding="utf-8")
        changed = ingest_knowledge_corpus(
            embedder=embedder,
            store=store,
            repo_root=root,
            relative_paths=[RUNBOOK],
            skip_unchanged=False,
        )
        assert changed.files == 1
        assert changed.deleted >= 1
        count_after_edit = store.count()
        assert count_after_edit < count_before * 2
        assert count_after_edit == count_before - changed.deleted + changed.indexed

        hits = _retrieve(store).execute(PROBE, top_k=8).hits
        documents = [hit.citation.document for hit in hits]
        assert RUNBOOK in documents
        assert any(PROBE in hit.text for hit in hits)
        assert any("Reindex probe" in hit.citation.section for hit in hits)

        path.write_text(original, encoding="utf-8")
        restored = ingest_knowledge_corpus(
            embedder=embedder,
            store=store,
            repo_root=root,
            relative_paths=[RUNBOOK],
            skip_unchanged=False,
        )
        assert restored.files == 1
        gone = _retrieve(store).execute(PROBE, top_k=8).hits
        assert not any(PROBE in hit.text for hit in gone)
        assert store.count() == count_before
    finally:
        path.write_text(original, encoding="utf-8")


def test_unchanged_full_ingest_does_not_grow_count(
    store: OpenSearchKnowledgeStore, tmp_path: Path
) -> None:
    embedder = FakeEmbedder()
    manifest = tmp_path / "manifest.json"
    first = ingest_knowledge_corpus(
        embedder=embedder,
        store=store,
        repo_root=repository_root(),
        skip_unchanged=True,
        manifest_path=manifest,
    )
    count = store.count()
    second = ingest_knowledge_corpus(
        embedder=embedder,
        store=store,
        repo_root=repository_root(),
        skip_unchanged=True,
        manifest_path=manifest,
    )
    assert first.files == 24
    assert second.skipped == 24
    assert second.indexed == 0
    assert store.count() == count

    third = ingest_knowledge_corpus(
        embedder=embedder,
        store=store,
        repo_root=repository_root(),
        skip_unchanged=False,
    )
    assert third.files == 24
    assert store.count() == count
