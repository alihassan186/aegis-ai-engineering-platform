"""RRF hybrid merge is isolated from OpenSearch (Step 3.5)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from aegis.application.rag.eval import load_eval_cases
from aegis.application.rag.retrieve import (
    RetrieveFilters,
    RetrieveHit,
    RetrieveKnowledge,
    merge_hybrid_rankings,
)
from aegis.core.protocols import KnowledgeHit
from aegis.infrastructure.rag.embedder import FakeEmbedder
from aegis.shared.exceptions import ValidationError


def _hit(chunk_id: str, path: str, score: float = 1.0) -> KnowledgeHit:
    return KnowledgeHit(
        chunk_id=chunk_id,
        text=f"body of {chunk_id}",
        source_path=path,
        section="Context",
        score=score,
    )


def test_rrf_prefers_docs_high_in_both_lists() -> None:
    bm25 = [
        _hit("a", "docs/a.md", 10.0),
        _hit("b", "docs/b.md", 8.0),
        _hit("c", "docs/c.md", 2.0),
    ]
    knn = [
        _hit("c", "docs/c.md", 0.9),
        _hit("a", "docs/a.md", 0.8),
        _hit("d", "docs/d.md", 0.7),
    ]
    fused = merge_hybrid_rankings(bm25, knn, top_k=3)
    assert [hit.chunk_id for hit in fused][0] == "a"
    assert {hit.chunk_id for hit in fused} <= {"a", "b", "c", "d"}
    assert all(hit.score > 0 for hit in fused)


def test_rrf_respects_top_k() -> None:
    bm25 = [_hit(f"c{i}", f"docs/{i}.md") for i in range(10)]
    fused = merge_hybrid_rankings(bm25, [], top_k=5)
    assert len(fused) == 5
    assert [hit.chunk_id for hit in fused] == [f"c{i}" for i in range(5)]


def test_rrf_includes_knn_only_docs() -> None:
    bm25 = [_hit("only-bm25", "docs/bm25.md")]
    knn = [_hit("only-knn", "docs/knn.md")]
    fused = merge_hybrid_rankings(bm25, knn, top_k=2)
    assert {hit.chunk_id for hit in fused} == {"only-bm25", "only-knn"}


def test_rrf_does_not_emit_embeddings() -> None:
    fused = merge_hybrid_rankings(
        [_hit("x", "docs/x.md")],
        [_hit("x", "docs/x.md")],
        top_k=1,
    )
    assert fused[0].__dataclass_fields__.keys() == {
        "chunk_id",
        "text",
        "source_path",
        "section",
        "score",
    }


class _MemorySearchStore:
    def __init__(self, hits: list[KnowledgeHit]) -> None:
        self.hits = hits

    def ensure_hybrid_index(self) -> None:
        return None

    def bulk_upsert(self, documents: object) -> int:
        del documents
        return 0

    def count(self) -> int:
        return len(self.hits)

    def search_match(
        self,
        *,
        text: str,
        source_path: str | None = None,
        size: int = 5,
    ) -> list[dict[str, object]]:
        del text, source_path, size
        return []

    def search_text(
        self, *, query: str, filters: Mapping[str, str], size: int
    ) -> list[KnowledgeHit]:
        del query
        return self._filtered(filters)[:size]

    def search_knn(
        self,
        *,
        embedding: Sequence[float],
        filters: Mapping[str, str],
        size: int,
    ) -> list[KnowledgeHit]:
        del embedding
        return list(reversed(self._filtered(filters)))[:size]

    def _filtered(self, filters: Mapping[str, str]) -> list[KnowledgeHit]:
        scenario = filters.get("scenario")
        if not scenario:
            return list(self.hits)
        if scenario == "latency_spike":
            return [hit for hit in self.hits if "latency" in hit.source_path]
        return []


def test_retrieve_builds_citations_and_applies_filters() -> None:
    store = _MemorySearchStore(
        [
            _hit("lat", "docs/knowledge/runbooks/payment-latency-spike.md"),
            _hit("db", "docs/knowledge/runbooks/payment-db-exhaustion.md"),
        ]
    )
    retrieve = RetrieveKnowledge(embedder=FakeEmbedder(), store=store)
    result = retrieve.execute(
        "payment p99",
        filters=RetrieveFilters(doc_type="runbook", scenario="latency_spike"),
        top_k=5,
    )
    assert result.hits
    assert all(
        hit.citation.document == "docs/knowledge/runbooks/payment-latency-spike.md"
        for hit in result.hits
    )
    citation = result.hits[0].citation
    assert citation.chunk_id == "lat"
    assert citation.section == "Context"
    assert "embedding" not in hit_as_dict(result.hits[0])


def test_retrieve_rejects_empty_query() -> None:
    retrieve = RetrieveKnowledge(embedder=FakeEmbedder(), store=_MemorySearchStore([]))
    with pytest.raises(ValidationError, match="non-empty"):
        retrieve.execute("   ")


def test_eval_queries_file_is_not_an_expected_document() -> None:
    cases = load_eval_cases()
    assert len(cases) == 16
    for case in cases:
        assert all("queries.jsonl" not in doc for doc in case.expected_docs)
        assert all("queries.jsonl" not in doc for doc in case.must_not)


def hit_as_dict(hit: RetrieveHit) -> dict[str, object]:
    return {
        "text": hit.text,
        "score": hit.score,
        "citation": {
            "document": hit.citation.document,
            "section": hit.citation.section,
            "chunk_id": hit.citation.chunk_id,
        },
    }
