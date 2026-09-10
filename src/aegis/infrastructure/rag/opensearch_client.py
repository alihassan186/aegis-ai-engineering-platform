"""OpenSearch adapter for the knowledge corpus (Step 3.4). Stdlib HTTP only."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

from aegis.core.protocols import KnowledgeHit
from aegis.infrastructure.rag.cluster import KNOWLEDGE_INDEX
from aegis.infrastructure.rag.embedder import EMBEDDING_DIMENSION
from aegis.infrastructure.rag.mappings import knowledge_index_body

_BULK_BATCH_SIZE = 50


class OpenSearchKnowledgeStore:
    """Bulk-upsert chunks into ``aegis-knowledge``. ``_id`` is ``chunk_id``."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 60.0) -> None:
        url = base_url.strip().rstrip("/")
        if not url:
            raise ValueError("OpenSearch URL is required (set AEGIS_OPENSEARCH_URL).")
        self._base = url
        self._timeout = timeout_seconds

    def ensure_hybrid_index(self) -> None:
        """Create or recreate the index when text + knn_vector mapping is missing."""
        existing = self._get_index()
        if existing is not None and _is_hybrid_mapping(existing):
            return
        if existing is not None:
            self._request("DELETE", f"/{KNOWLEDGE_INDEX}")
        self._request("PUT", f"/{KNOWLEDGE_INDEX}", body=knowledge_index_body())

    def bulk_upsert(self, documents: Sequence[Mapping[str, Any]]) -> int:
        """Index documents by ``chunk_id``. Same id overwrites (Step 3.6 reindex)."""
        if not documents:
            return 0
        written = 0
        for offset in range(0, len(documents), _BULK_BATCH_SIZE):
            batch = documents[offset : offset + _BULK_BATCH_SIZE]
            payload = _bulk_ndjson(batch)
            response = self._request(
                "POST",
                "/_bulk?refresh=false",
                body=payload,
                content_type="application/x-ndjson",
            )
            _raise_if_bulk_errors(response)
            written += len(batch)
        self._request("POST", f"/{KNOWLEDGE_INDEX}/_refresh")
        return written

    def count(self) -> int:
        payload = self._request("GET", f"/{KNOWLEDGE_INDEX}/_count")
        count = payload.get("count") if isinstance(payload, dict) else None
        if not isinstance(count, int):
            raise ConnectionError("OpenSearch _count did not return an integer.")
        return count

    def search_match(
        self,
        *,
        text: str,
        source_path: str | None = None,
        size: int = 5,
    ) -> list[dict[str, Any]]:
        """BM25 ``match`` on ``text``. Used by ingest tests; retrieve API is Step 3.5."""
        must: list[dict[str, Any]] = [{"match": {"text": text}}]
        filters: list[dict[str, Any]] = []
        if source_path:
            filters.append({"term": {"source_path": source_path}})
        query: dict[str, Any]
        if filters:
            query = {"bool": {"must": must, "filter": filters}}
        else:
            query = must[0]
        payload = self._request(
            "POST",
            f"/{KNOWLEDGE_INDEX}/_search",
            body={
                "query": query,
                "size": size,
                "_source": {"excludes": ["embedding"]},
            },
        )
        hits = payload.get("hits", {}).get("hits", []) if isinstance(payload, dict) else []
        sources: list[dict[str, Any]] = []
        for hit in hits:
            source = hit.get("_source")
            if isinstance(source, dict):
                sources.append(source)
        return sources

    def search_text(
        self,
        *,
        query: str,
        filters: Mapping[str, str],
        size: int,
    ) -> list[KnowledgeHit]:
        """BM25 match on ``text`` with FR-042 filter clauses. Embeddings excluded."""
        body = {
            "query": {
                "bool": {
                    "must": [{"match": {"text": query}}],
                    "filter": _filter_clauses(filters),
                }
            },
            "size": size,
            "_source": {"excludes": ["embedding"]},
        }
        payload = self._request("POST", f"/{KNOWLEDGE_INDEX}/_search", body=body)
        return _hits_from_search(payload)

    def search_knn(
        self,
        *,
        embedding: Sequence[float],
        filters: Mapping[str, str],
        size: int,
    ) -> list[KnowledgeHit]:
        """kNN on ``embedding`` with the same filters. Embeddings excluded from _source."""
        k = max(1, size)
        body = {
            "size": k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": [float(value) for value in embedding],
                                    "k": k,
                                }
                            }
                        }
                    ],
                    "filter": _filter_clauses(filters),
                }
            },
            "_source": {"excludes": ["embedding"]},
        }
        payload = self._request("POST", f"/{KNOWLEDGE_INDEX}/_search", body=body)
        return _hits_from_search(payload)

    def mapping_properties(self) -> dict[str, Any]:
        payload = self._request("GET", f"/{KNOWLEDGE_INDEX}/_mapping")
        index = payload.get(KNOWLEDGE_INDEX, payload) if isinstance(payload, dict) else {}
        properties = index.get("mappings", {}).get("properties", {})
        if not isinstance(properties, dict):
            return {}
        return properties

    def _get_index(self) -> dict[str, Any] | None:
        url = f"{self._base}/{KNOWLEDGE_INDEX}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                return None
            raise ConnectionError(
                f"OpenSearch GET /{KNOWLEDGE_INDEX} failed: HTTP {exc.code}: {body[:2000]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"OpenSearch is not reachable at {url}") from exc
        if not isinstance(payload, dict):
            raise ConnectionError("OpenSearch GET index response was not an object.")
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | bytes | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        url = f"{self._base}{path}"
        data: bytes | None
        headers: dict[str, str] = {}
        if body is None:
            data = None
        elif isinstance(body, bytes):
            data = body
            headers["Content-Type"] = content_type
        else:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            raise ConnectionError(
                f"OpenSearch {method} {path} failed: HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"OpenSearch is not reachable at {url}") from exc
        if not raw:
            return {}
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ConnectionError(f"OpenSearch {method} {path} returned a non-object.")
        return payload


def _is_hybrid_mapping(payload: dict[str, Any]) -> bool:
    index = payload.get(KNOWLEDGE_INDEX, payload)
    properties = index.get("mappings", {}).get("properties", {}) if isinstance(index, dict) else {}
    embedding = properties.get("embedding", {}) if isinstance(properties, dict) else {}
    text = properties.get("text", {}) if isinstance(properties, dict) else {}
    return (
        isinstance(embedding, dict)
        and embedding.get("type") == "knn_vector"
        and embedding.get("dimension") == EMBEDDING_DIMENSION
        and isinstance(text, dict)
        and text.get("type") == "text"
        and "incident_id" in properties
    )


def _bulk_ndjson(documents: Sequence[Mapping[str, Any]]) -> bytes:
    lines: list[str] = []
    for document in documents:
        chunk_id = document.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError("Each bulk document must include a non-empty chunk_id.")
        meta = {"index": {"_index": KNOWLEDGE_INDEX, "_id": chunk_id}}
        lines.append(json.dumps(meta, separators=(",", ":")))
        lines.append(json.dumps(dict(document), separators=(",", ":")))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _raise_if_bulk_errors(payload: Mapping[str, Any]) -> None:
    if not payload.get("errors"):
        return
    details: list[str] = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        action: dict[str, Any] = next(iter(item.values()), {})
        if not isinstance(action, dict):
            continue
        error = action.get("error")
        status = action.get("status", 0)
        if error or (isinstance(status, int) and status >= 300):
            details.append(json.dumps(action)[:500])
        if len(details) >= 5:
            break
    joined = "; ".join(details) if details else json.dumps(dict(payload))[:1000]
    raise ConnectionError(f"OpenSearch bulk indexing failed: {joined}")


def _filter_clauses(filters: Mapping[str, str]) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = [{"term": {"role": "child"}}]
    for field in ("service", "doc_type", "scenario", "incident_id", "source_path"):
        value = str(filters.get(field, "")).strip()
        if value:
            clauses.append({"term": {field: value}})
    date_from = str(filters.get("date_from", "")).strip()
    date_to = str(filters.get("date_to", "")).strip()
    if date_from or date_to:
        bounds: dict[str, str] = {}
        if date_from:
            bounds["gte"] = date_from
        if date_to:
            bounds["lte"] = date_to
        clauses.append({"range": {"date": bounds}})
    return clauses


def _hits_from_search(payload: Mapping[str, Any]) -> list[KnowledgeHit]:
    raw_hits = payload.get("hits", {}).get("hits", []) if isinstance(payload, dict) else []
    hits: list[KnowledgeHit] = []
    for item in raw_hits:
        if not isinstance(item, dict):
            continue
        source = item.get("_source")
        if not isinstance(source, dict):
            continue
        chunk_id = str(source.get("chunk_id") or item.get("_id") or "")
        if not chunk_id:
            continue
        score = item.get("_score")
        hits.append(
            KnowledgeHit(
                chunk_id=chunk_id,
                text=str(source.get("text") or ""),
                source_path=str(source.get("source_path") or ""),
                section=str(source.get("section") or ""),
                score=float(score) if isinstance(score, (int, float)) else 0.0,
            )
        )
    return hits
