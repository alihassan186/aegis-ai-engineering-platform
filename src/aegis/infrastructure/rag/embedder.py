"""Dense embedders for RAG (Step 3.3). Vectors only — no Claude, no OpenSearch write."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from typing import Any

from aegis.config.settings import Settings
from aegis.core.protocols import Embedder

# Titan Text Embeddings V2 (ADR-004). Keep Fake at the same size for 3.4 mappings.
EMBEDDING_DIMENSION = 1024
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"
# Titan v2 accepts one inputText per InvokeModel; we still cap list size per call.
MAX_TEXTS_PER_CALL = 8


def build_embedder(settings: Settings | None = None) -> Embedder:
    """Compose Fake vs Titan from env. Default is fake (tests / local without AWS)."""
    resolved = settings or Settings.from_env()
    if resolved.embedder == "fake":
        return FakeEmbedder()
    if resolved.embedder == "titan":
        if not resolved.aws_region:
            raise ValueError(
                "AEGIS_AWS_REGION (or AWS_REGION) is required when AEGIS_EMBEDDER=titan."
            )
        return TitanEmbedder(region=resolved.aws_region)
    raise ValueError(f"Unknown embedder {resolved.embedder!r}; use fake or titan.")


class FakeEmbedder:
    """Deterministic 1024-d hash projection. No network. Not for production quality."""

    dimension = EMBEDDING_DIMENSION

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        _reject_empty_texts(texts)
        return [_fake_vector(text) for text in texts]


class TitanEmbedder:
    """Bedrock Runtime ``InvokeModel`` for Titan V2. IAM from the environment (NFR-034)."""

    dimension = EMBEDDING_DIMENSION

    def __init__(
        self,
        *,
        region: str,
        model_id: str = TITAN_MODEL_ID,
        client: Any | None = None,
    ) -> None:
        if not region.strip():
            raise ValueError("TitanEmbedder requires a non-empty AWS region.")
        self._region = region.strip()
        self._model_id = model_id
        self._client = client if client is not None else _bedrock_runtime_client(self._region)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        _reject_empty_texts(texts)
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), MAX_TEXTS_PER_CALL):
            batch = texts[offset : offset + MAX_TEXTS_PER_CALL]
            for text in batch:
                vectors.append(self._invoke_one(text))
        return vectors

    def _invoke_one(self, text: str) -> list[float]:
        body = json.dumps(
            {"inputText": text, "dimensions": EMBEDDING_DIMENSION, "normalize": True}
        )
        try:
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except Exception as exc:
            raise ConnectionError(
                "Bedrock Titan InvokeModel failed. Check IAM (bedrock:InvokeModel), "
                f"region {self._region!r}, and that AEGIS_EMBEDDER=titan is intended."
            ) from exc
        raw = response["body"].read() if hasattr(response["body"], "read") else response["body"]
        if isinstance(raw, bytes):
            payload = json.loads(raw.decode("utf-8"))
        else:
            payload = json.loads(raw)
        embedding = payload.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != EMBEDDING_DIMENSION:
            raise ConnectionError("Titan response did not contain a 1024-d embedding.")
        return [float(value) for value in embedding]


def _bedrock_runtime_client(region: str) -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required when AEGIS_EMBEDDER=titan. Install project dependencies."
        ) from exc
    return boto3.client("bedrock-runtime", region_name=region)


def _reject_empty_texts(texts: list[str]) -> None:
    if not texts:
        return
    for index, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"embed_texts rejects empty strings (index {index}). "
                "Chunk text must be non-empty."
            )


def _fake_vector(text: str) -> list[float]:
    raw = hashlib.shake_256(text.encode("utf-8")).digest(EMBEDDING_DIMENSION * 4)
    ints = struct.unpack(f"<{EMBEDDING_DIMENSION}i", raw)
    vec = [float(value) for value in ints]
    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]
