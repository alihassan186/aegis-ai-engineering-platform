"""Hybrid retrieve with citations (Step 3.5). No OpenSearch, no Claude."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from aegis.core.protocols import Embedder, KnowledgeHit, KnowledgeStore
from aegis.shared.exceptions import ValidationError

DEFAULT_TOP_K = 5
MAX_TOP_K = 20
# RRF_K is the "Rerank Fusion k" parameter: the number of top results to consider from each retrieval method (e.g., BM25 and KNN) in Reciprocal Rank Fusion (RRF) retrieval. See: https://en.wikipedia.org/wiki/Reciprocal_rank_fusion
RRF_K = 60
BM25_WEIGHT = 0.7
KNN_WEIGHT = 0.3
_FILTER_KEYS = ("service", "doc_type", "scenario", "date_from", "date_to", "incident_id")


@dataclass(frozen=True, slots=True)
class RetrieveFilters:
    """FR-042 metadata filters. Empty strings are ignored."""

    service: str | None = None
    doc_type: str | None = None
    scenario: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    incident_id: str | None = None

    def as_mapping(self) -> dict[str, str]:
        raw = {
            "service": self.service,
            "doc_type": self.doc_type,
            "scenario": self.scenario,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "incident_id": self.incident_id,
        }
        return {key: value.strip() for key, value in raw.items() if value and value.strip()}


@dataclass(frozen=True, slots=True)
class Citation:
    """FR-044: document path, heading section, chunk id."""

    document: str
    section: str
    chunk_id: str


@dataclass(frozen=True, slots=True)
class RetrieveHit:
    """One ranked chunk. ``text`` is data, not instructions (NFR-036)."""

    text: str
    score: float
    citation: Citation


@dataclass(frozen=True, slots=True)
class RetrieveResult:
    hits: list[RetrieveHit] = field(default_factory=list)


def merge_hybrid_rankings(
    bm25: Sequence[KnowledgeHit],
    knn: Sequence[KnowledgeHit],
    *,
    top_k: int,
    rrf_k: int = RRF_K,
    bm25_weight: float = BM25_WEIGHT,
    knn_weight: float = KNN_WEIGHT,
) -> list[KnowledgeHit]:
    """Reciprocal rank fusion. Isolated so tests do not need OpenSearch."""
    if top_k < 1:
        raise ValidationError("top_k must be at least 1.")
    by_id: dict[str, KnowledgeHit] = {}
    scores: dict[str, float] = {}
    for rank, hit in enumerate(bm25, start=1):
        by_id[hit.chunk_id] = hit
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + bm25_weight / (rrf_k + rank)
    for rank, hit in enumerate(knn, start=1):
        by_id.setdefault(hit.chunk_id, hit)
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + knn_weight / (rrf_k + rank)
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    fused: list[KnowledgeHit] = []
    for chunk_id in ordered[:top_k]:
        hit = by_id[chunk_id]
        fused.append(
            KnowledgeHit(
                chunk_id=hit.chunk_id,
                text=hit.text,
                source_path=hit.source_path,
                section=hit.section,
                score=scores[chunk_id],
            )
        )
    return fused


def candidate_size(top_k: int) -> int:
    return min(50, max(20, top_k * 4))


class RetrieveKnowledge:
    """Embed query → BM25 + kNN → RRF. Does not call Claude or LangGraph."""

    def __init__(self, *, embedder: Embedder, store: KnowledgeStore) -> None:
        self._embedder = embedder
        self._store = store

    def execute(
        self,
        query: str,
        *,
        filters: RetrieveFilters | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrieveResult:
        text = query.strip()
        if not text:
            raise ValidationError("Retrieve query must be a non-empty string.")
        if top_k < 1 or top_k > MAX_TOP_K:
            raise ValidationError(f"top_k must be between 1 and {MAX_TOP_K}.")
        resolved = filters or RetrieveFilters()
        mapping = resolved.as_mapping()
        size = candidate_size(top_k)
        vectors = self._embedder.embed_texts([text])
        bm25 = self._store.search_text(query=text, filters=mapping, size=size)
        knn = self._store.search_knn(embedding=vectors[0], filters=mapping, size=size)
        fused = merge_hybrid_rankings(bm25, knn, top_k=top_k)
        return RetrieveResult(hits=[_to_retrieve_hit(hit) for hit in fused])


def _to_retrieve_hit(hit: KnowledgeHit) -> RetrieveHit:
    return RetrieveHit(
        text=hit.text,
        score=hit.score,
        citation=Citation(
            document=hit.source_path,
            section=hit.section,
            chunk_id=hit.chunk_id,
        ),
    )


def assert_known_filter_keys(filters: Mapping[str, str]) -> None:
    unknown = [key for key in filters if key not in _FILTER_KEYS]
    if unknown:
        raise ValidationError(f"Unknown retrieve filters: {', '.join(sorted(unknown))}.")
