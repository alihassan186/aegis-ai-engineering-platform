"""Index settings + mappings for ``aegis-knowledge`` (FR-043).

``mappings.json`` is the operator-readable copy. This module loads it so the
OpenSearch client and tests share one definition. Dimension must stay 1024
(Titan V2 / FakeEmbedder).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aegis.infrastructure.rag.embedder import EMBEDDING_DIMENSION

_MAPPINGS_PATH = Path(__file__).with_name("mappings.json")

REQUIRED_SOURCE_FIELDS = (
    "text",
    "embedding",
    "source_path",
    "section",
    "doc_type",
    "service",
    "scenario",
    "date",
    "chunk_id",
)


def knowledge_index_body() -> dict[str, Any]:
    """PUT body for ``aegis-knowledge``: BM25 ``text`` + ``knn_vector`` embedding."""
    body = json.loads(_MAPPINGS_PATH.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError("mappings.json must be a JSON object.")
    properties = body.get("mappings", {}).get("properties", {})
    embedding = properties.get("embedding", {})
    if embedding.get("type") != "knn_vector":
        raise ValueError("mappings.json embedding must be knn_vector.")
    if embedding.get("dimension") != EMBEDDING_DIMENSION:
        raise ValueError(
            f"mappings.json embedding.dimension must be {EMBEDDING_DIMENSION}."
        )
    missing = [name for name in REQUIRED_SOURCE_FIELDS if name not in properties]
    if missing:
        raise ValueError(f"mappings.json missing fields: {', '.join(missing)}")
    return body
