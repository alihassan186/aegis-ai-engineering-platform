"""FakeEmbedder is deterministic and 1024-d; Titan is optional (Step 3.3)."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from aegis.config.settings import Settings
from aegis.core.protocols import Embedder
from aegis.infrastructure.rag.embedder import (
    EMBEDDING_DIMENSION,
    FakeEmbedder,
    TitanEmbedder,
    build_embedder,
)


def test_fake_identical_text_identical_vector() -> None:
    embedder = FakeEmbedder()
    first = embedder.embed_texts(["payment p99 latency"])
    second = embedder.embed_texts(["payment p99 latency"])
    assert first == second
    assert len(first) == 1
    assert len(first[0]) == EMBEDDING_DIMENSION == 1024


def test_fake_preserves_batch_order() -> None:
    embedder = FakeEmbedder()
    texts = ["alpha", "beta", "gamma"]
    vectors = embedder.embed_texts(texts)
    assert [embedder.embed_texts([text])[0] for text in texts] == vectors


def test_fake_different_texts_differ() -> None:
    embedder = FakeEmbedder()
    left, right = embedder.embed_texts(["payment latency", "notification backlog"])
    assert left != right


def test_fake_rejects_empty_string() -> None:
    embedder = FakeEmbedder()
    with pytest.raises(ValueError, match="empty"):
        embedder.embed_texts(["ok", "  "])
    with pytest.raises(ValueError, match="empty"):
        embedder.embed_texts([""])


def test_fake_empty_list_returns_empty() -> None:
    assert FakeEmbedder().embed_texts([]) == []


def test_build_embedder_defaults_to_fake() -> None:
    settings = Settings(environment="test", embedder="fake")
    embedder = build_embedder(settings)
    assert isinstance(embedder, FakeEmbedder)
    assert isinstance(embedder, Embedder)


def test_titan_requires_region() -> None:
    with pytest.raises(ValueError, match="region"):
        TitanEmbedder(region="")
    with pytest.raises(ValueError, match="AEGIS_AWS_REGION"):
        build_embedder(Settings(embedder="titan", aws_region=""))


def test_titan_parses_invoke_model_without_network() -> None:
    payload = json.dumps({"embedding": [0.0] * 1023 + [1.0]}).encode("utf-8")

    class _Client:
        def invoke_model(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["modelId"] == "amazon.titan-embed-text-v2:0"
            body = json.loads(str(kwargs["body"]))
            assert body["dimensions"] == 1024
            return {"body": SimpleNamespace(read=lambda: payload)}

    embedder = TitanEmbedder(region="eu-west-1", client=_Client())
    vectors = embedder.embed_texts(["checkout"])
    assert len(vectors[0]) == 1024
    assert vectors[0][-1] == 1.0


@pytest.mark.integration
def test_titan_live_skipped_without_opt_in() -> None:
    if os.getenv("AEGIS_RUN_TITAN_TEST") != "1":
        pytest.skip("Set AEGIS_RUN_TITAN_TEST=1 and AWS credentials to call Bedrock.")
    region = os.getenv("AEGIS_AWS_REGION") or os.getenv("AWS_REGION") or ""
    if not region:
        pytest.skip("AEGIS_AWS_REGION is required for the live Titan test.")
    embedder = TitanEmbedder(region=region)
    vectors = embedder.embed_texts(["AEGIS RAG embedding probe"])
    assert len(vectors[0]) == 1024
