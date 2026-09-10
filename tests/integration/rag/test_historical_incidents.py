"""FR-041 gate: six written INC-* RCAs are in aegis-knowledge, not live Postgres."""

from __future__ import annotations

import os
import re

import pytest

from aegis.application.rag.allowlist import ALLOWED_RELATIVE_PATHS, repository_root
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.application.rag.retrieve import RetrieveFilters, RetrieveKnowledge
from aegis.infrastructure.rag.embedder import FakeEmbedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore

HISTORICAL_RCAS: tuple[str, ...] = tuple(
    path for path in ALLOWED_RELATIVE_PATHS if path.startswith("docs/knowledge/incidents/INC-2026-")
)
DB_EXHAUSTION_RCA = "docs/knowledge/incidents/INC-2026-0511-db-exhaustion.md"
LATENCY_RCA = "docs/knowledge/incidents/INC-2026-0412-payment-latency.md"
LATENCY_RUNBOOK = "docs/knowledge/runbooks/payment-latency-spike.md"
WEBHOOK_SHAPED_TITLE = "Latency spike on payment"
_UUID_PATH = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def opensearch_url() -> str:
    url = os.getenv("AEGIS_OPENSEARCH_URL", "").strip().rstrip("/")
    if not url:
        pytest.skip("AEGIS_OPENSEARCH_URL is unset; OpenSearch is optional for this suite.")
    return url


@pytest.fixture(scope="module")
def store(opensearch_url: str) -> OpenSearchKnowledgeStore:
    client = OpenSearchKnowledgeStore(opensearch_url)
    ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=client,
        repo_root=repository_root(),
        skip_unchanged=False,
    )
    return client


def _retrieve(store: OpenSearchKnowledgeStore) -> RetrieveKnowledge:
    return RetrieveKnowledge(embedder=FakeEmbedder(), store=store)


def test_allowlist_has_exactly_six_written_rcas() -> None:
    assert len(HISTORICAL_RCAS) == 6
    for rel in HISTORICAL_RCAS:
        assert (repository_root() / rel).is_file()


def test_all_six_rca_source_paths_are_in_the_index(store: OpenSearchKnowledgeStore) -> None:
    for rel in HISTORICAL_RCAS:
        hits = store.search_text(
            query="closed",
            filters={"doc_type": "incident_report", "source_path": rel},
            size=5,
        )
        assert hits, f"written RCA not in aegis-knowledge: {rel}"
        assert all(hit.source_path == rel for hit in hits)
        assert all(hit.chunk_id.startswith(f"{rel}#") for hit in hits)
        assert all(not _UUID_PATH.match(hit.source_path) for hit in hits)

    broad = store.search_text(
        query="closed",
        filters={"doc_type": "incident_report"},
        size=50,
    )
    indexed = {hit.source_path for hit in broad}
    extra = sorted(path for path in indexed if path not in HISTORICAL_RCAS)
    assert extra == []
    assert all(hit.section for hit in broad)
    assert all(not _UUID_PATH.match(hit.source_path) for hit in broad)
    assert all("/api/v1/incidents" not in hit.source_path for hit in broad)


def test_db_exhaustion_filter_returns_written_rca_not_runbook(
    store: OpenSearchKnowledgeStore,
) -> None:
    result = _retrieve(store).execute(
        "Historical incident where checkout Postgres ran out of connections",
        filters=RetrieveFilters(doc_type="incident_report", scenario="db_exhaustion"),
        top_k=8,
    )
    assert result.hits
    documents = [hit.citation.document for hit in result.hits]
    assert set(documents) == {DB_EXHAUSTION_RCA}
    assert LATENCY_RCA not in documents
    assert "docs/knowledge/runbooks/payment-db-exhaustion.md" not in documents
    hit = result.hits[0]
    assert hit.citation.section
    assert hit.citation.chunk_id.startswith(f"{DB_EXHAUSTION_RCA}#")
    assert "embedding" not in hit.__dataclass_fields__


def test_webhook_shaped_title_is_not_the_indexed_document(
    store: OpenSearchKnowledgeStore,
) -> None:
    """Live ingest titles are not required; the markdown RCA is what retrieve cites."""
    result = _retrieve(store).execute(
        WEBHOOK_SHAPED_TITLE,
        filters=RetrieveFilters(doc_type="incident_report", scenario="latency_spike"),
        top_k=8,
    )
    assert result.hits
    documents = [hit.citation.document for hit in result.hits]
    assert set(documents) == {LATENCY_RCA}
    assert LATENCY_RUNBOOK not in documents
    assert all(path.startswith("docs/knowledge/incidents/") for path in documents)
    assert not any(_UUID_PATH.match(path) for path in documents)
    assert all("/api/v1/incidents" not in path for path in documents)
    assert result.hits[0].citation.section
    assert result.hits[0].citation.chunk_id.startswith(f"{LATENCY_RCA}#")
