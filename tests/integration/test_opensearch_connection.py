"""OpenSearch is reachable when AEGIS_OPENSEARCH_URL is set (Step 3.1)."""

from __future__ import annotations

import os

import pytest

from aegis.infrastructure.rag.cluster import KNOWLEDGE_INDEX, cluster_health, ensure_knowledge_index


@pytest.fixture
def opensearch_url() -> str:
    url = os.getenv("AEGIS_OPENSEARCH_URL", "").strip().rstrip("/")
    if not url:
        pytest.skip("AEGIS_OPENSEARCH_URL is unset; OpenSearch is optional for this suite.")
    return url


def test_cluster_health_is_yellow_or_green(opensearch_url: str) -> None:
    health = cluster_health(opensearch_url)
    assert health.get("status") in {"yellow", "green"}


def test_knowledge_index_exists(opensearch_url: str) -> None:
    ensure_knowledge_index(opensearch_url)
    health = cluster_health(opensearch_url)
    assert health.get("status") in {"yellow", "green"}
    assert KNOWLEDGE_INDEX == "aegis-knowledge"
