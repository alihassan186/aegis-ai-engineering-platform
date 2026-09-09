"""FR-043 index mapping: BM25 text + 1024-d knn_vector."""

from __future__ import annotations

import json
from pathlib import Path

from aegis.infrastructure.rag.embedder import EMBEDDING_DIMENSION
from aegis.infrastructure.rag.mappings import REQUIRED_SOURCE_FIELDS, knowledge_index_body


def test_knowledge_mapping_has_text_and_knn_vector() -> None:
    body = knowledge_index_body()
    properties = body["mappings"]["properties"]
    assert body["settings"]["index"]["knn"] is True
    assert properties["text"]["type"] == "text"
    assert properties["text"]["analyzer"] == "standard"
    assert properties["embedding"]["type"] == "knn_vector"
    assert properties["embedding"]["dimension"] == EMBEDDING_DIMENSION == 1024
    for field in REQUIRED_SOURCE_FIELDS:
        assert field in properties


def test_mappings_json_matches_loader() -> None:
    path = Path(__file__).resolve().parents[3] / "src/aegis/infrastructure/rag/mappings.json"
    assert json.loads(path.read_text(encoding="utf-8")) == knowledge_index_body()
