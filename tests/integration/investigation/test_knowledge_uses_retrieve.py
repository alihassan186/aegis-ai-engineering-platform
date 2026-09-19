"""Live RetrieveKnowledge through the knowledge specialist (Step 4.5)."""

from __future__ import annotations

import os

import pytest

from aegis.application.investigation.collect import collect_knowledge
from aegis.application.rag.allowlist import repository_root
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.application.rag.retrieve import RetrieveKnowledge
from aegis.infrastructure.rag.embedder import FakeEmbedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore

LATENCY_RUNBOOK = "docs/knowledge/runbooks/payment-latency-spike.md"
DB_RUNBOOK = "docs/knowledge/runbooks/payment-db-exhaustion.md"


@pytest.fixture(scope="module")
def opensearch_url() -> str:
    url = os.getenv("AEGIS_OPENSEARCH_URL", "").strip().rstrip("/")
    if not url:
        pytest.skip("AEGIS_OPENSEARCH_URL is unset; OpenSearch is optional for this suite.")
    return url


@pytest.fixture(scope="module")
def store(opensearch_url: str) -> OpenSearchKnowledgeStore:
    client = OpenSearchKnowledgeStore(opensearch_url)
    try:
        ingest_knowledge_corpus(
            embedder=FakeEmbedder(),
            store=client,
            repo_root=repository_root(),
            skip_unchanged=False,
        )
    except ConnectionError:
        pytest.skip("OpenSearch is not reachable; live retrieve is optional.")
    return client


def test_knowledge_uses_retrieve_for_latency_runbook(store: OpenSearchKnowledgeStore) -> None:
    retrieve = RetrieveKnowledge(embedder=FakeEmbedder(), store=store)
    update = collect_knowledge(
        {
            "incident_id": "INC-LIVE",
            "service": "payment",
            "scenario": "latency_spike",
            "hops": 1,
            "next_agent": "knowledge",
            "status": "running",
            "human_decision": "",
            "evidence": [],
            "log": [],
            "failed_steps": [],
        },  # type: ignore[arg-type]
        retrieve,
    )
    documents = [item["citation"]["document"] for item in update["evidence"]]
    assert documents
    assert all(
        doc.startswith("docs/knowledge/") or doc.startswith("docs/adr/") for doc in documents
    )
    assert LATENCY_RUNBOOK in documents
    assert DB_RUNBOOK not in documents
    assert all(item["text_role"] == "data" for item in update["evidence"])
