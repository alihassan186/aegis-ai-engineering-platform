"""POST /api/v1/retrieve (JWT). Skips without AEGIS_OPENSEARCH_URL. No Postgres."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aegis.application.rag.allowlist import repository_root
from aegis.application.rag.eval import EVAL_TOP_K, load_eval_cases, score_eval_dataset
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.application.rag.retrieve import RetrieveKnowledge
from aegis.domain.auth.enums import Role
from aegis.infrastructure.rag.embedder import FakeEmbedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore
from aegis.main import create_app
from tests.helpers.auth import api_test_settings, authorization_header

ADR_002 = "docs/adr/ADR-002-postgresql.md"
LATENCY_RUNBOOK = "docs/knowledge/runbooks/payment-latency-spike.md"
DB_RUNBOOK = "docs/knowledge/runbooks/payment-db-exhaustion.md"
POSTGRES_QUERY = "Why is PostgreSQL the system of record for incidents and audit logs?"


@pytest.fixture(scope="module")
def opensearch_url() -> str:
    url = os.getenv("AEGIS_OPENSEARCH_URL", "").strip().rstrip("/")
    if not url:
        pytest.skip("AEGIS_OPENSEARCH_URL is unset; OpenSearch is optional for this suite.")
    return url


@pytest.fixture(scope="module")
def retrieve_client(opensearch_url: str) -> TestClient:
    ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=OpenSearchKnowledgeStore(opensearch_url),
        repo_root=repository_root(),
    )
    application = create_app(
        api_test_settings(opensearch_url=opensearch_url, embedder="fake")
    )
    return TestClient(application)


def test_retrieve_unauthenticated_returns_401(retrieve_client: TestClient) -> None:
    response = retrieve_client.post("/api/v1/retrieve", json={"query": "postgresql"})
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "UNAUTHENTICATED"
    assert error["request_id"]
    assert response.headers["www-authenticate"] == "Bearer"


def test_retrieve_postgresql_cites_adr_002(retrieve_client: TestClient) -> None:
    response = retrieve_client.post(
        "/api/v1/retrieve",
        json={"query": POSTGRES_QUERY, "top_k": 8},
        headers=authorization_header(Role.ENGINEER),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"]
    documents = [hit["citation"]["document"] for hit in body["hits"]]
    assert ADR_002 in documents
    hit = next(item for item in body["hits"] if item["citation"]["document"] == ADR_002)
    assert hit["text"]
    assert hit["citation"]["section"]
    assert hit["citation"]["chunk_id"].startswith(f"{ADR_002}#")
    assert "embedding" not in hit
    assert "embedding" not in hit["citation"]


def test_retrieve_latency_filter_excludes_db_exhaustion(retrieve_client: TestClient) -> None:
    response = retrieve_client.post(
        "/api/v1/retrieve",
        json={
            "query": "payment p99 latency spike",
            "top_k": 8,
            "filters": {"scenario": "latency_spike", "doc_type": "runbook"},
        },
        headers=authorization_header(Role.VIEWER),
    )
    assert response.status_code == 200
    documents = [hit["citation"]["document"] for hit in response.json()["hits"]]
    assert LATENCY_RUNBOOK in documents
    assert DB_RUNBOOK not in documents


def test_retrieve_without_opensearch_returns_503() -> None:
    application = create_app(api_test_settings(opensearch_url=""))
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/retrieve",
            json={"query": "postgresql"},
            headers=authorization_header(),
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SEARCH_NOT_CONFIGURED"


def test_queries_jsonl_expected_docs_in_top_8(opensearch_url: str) -> None:
    retrieve = RetrieveKnowledge(
        embedder=FakeEmbedder(),
        store=OpenSearchKnowledgeStore(opensearch_url),
    )
    ingest_knowledge_corpus(
        embedder=FakeEmbedder(),
        store=OpenSearchKnowledgeStore(opensearch_url),
        repo_root=repository_root(),
    )
    cases = load_eval_cases(repo_root=repository_root())
    assert len(cases) == 16
    results = score_eval_dataset(retrieve, cases, top_k=EVAL_TOP_K)
    failed = [row for row in results if not row.passed]
    assert failed == [], "; ".join(
        f"{row.case_id} missing={row.missing} forbidden={row.forbidden_hits}"
        for row in failed
    )
