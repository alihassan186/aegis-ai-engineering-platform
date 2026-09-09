"""Live ingest into local OpenSearch (Step 3.4). Skips without AEGIS_OPENSEARCH_URL."""

from __future__ import annotations

import os

import pytest

from aegis.application.rag.allowlist import ALLOWED_RELATIVE_PATHS, repository_root
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.infrastructure.rag.cluster import KNOWLEDGE_INDEX
from aegis.infrastructure.rag.embedder import EMBEDDING_DIMENSION, FakeEmbedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore

RUNBOOK = "docs/knowledge/runbooks/payment-latency-spike.md"


@pytest.fixture
def opensearch_url() -> str:
    url = os.getenv("AEGIS_OPENSEARCH_URL", "").strip().rstrip("/")
    if not url:
        pytest.skip("AEGIS_OPENSEARCH_URL is unset; OpenSearch is optional for this suite.")
    return url


@pytest.fixture
def store(opensearch_url: str) -> OpenSearchKnowledgeStore:
    return OpenSearchKnowledgeStore(opensearch_url)


def test_ingest_allowlist_count_and_match(store: OpenSearchKnowledgeStore) -> None:
    result = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
    )
    assert result.files == len(ALLOWED_RELATIVE_PATHS) == 24
    assert result.chunks == result.indexed
    assert store.count() == result.chunks
    assert store.count() >= 24
    assert KNOWLEDGE_INDEX == "aegis-knowledge"

    properties = store.mapping_properties()
    assert properties["text"]["type"] == "text"
    assert properties["embedding"]["type"] == "knn_vector"
    assert properties["embedding"]["dimension"] == EMBEDDING_DIMENSION

    hits = store.search_match(
        text="payment client timeout",
        source_path=RUNBOOK,
        size=5,
    )
    assert hits
    assert all(hit["source_path"] == RUNBOOK for hit in hits)
    assert all(hit.get("role") == "child" for hit in hits)


def test_reingest_does_not_duplicate(store: OpenSearchKnowledgeStore) -> None:
    first = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
    )
    second = ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=store,
        repo_root=repository_root(),
    )
    assert first.indexed == second.indexed
    assert store.count() == first.chunks
