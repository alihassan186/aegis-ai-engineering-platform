"""Local OpenSearch health and empty knowledge index (Step 3.1).

Index name ``aegis-knowledge`` is the RAG store. A future logs index may be
named ``aegis-logs`` — do not create or fill it here (telemetry is not RAG).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

KNOWLEDGE_INDEX = "aegis-knowledge"
# Reserved only: aegis-logs  — do not create in v0.4 Step 3.1.


def cluster_health(base_url: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """GET /_cluster/health. ``base_url`` comes from settings (no hardcoded host)."""
    url = f"{base_url.rstrip('/')}/_cluster/health"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(f"OpenSearch is not reachable at {url}") from exc
    if not isinstance(payload, dict):
        raise ConnectionError("OpenSearch health response was not an object.")
    return payload


def ensure_knowledge_index(base_url: str, *, timeout_seconds: float = 5.0) -> None:
    """Create ``aegis-knowledge`` if missing. No documents, no knn mapping (Step 3.4)."""
    root = base_url.rstrip("/")
    index_url = f"{root}/{KNOWLEDGE_INDEX}"
    get = urllib.request.Request(index_url, method="GET")
    try:
        with urllib.request.urlopen(get, timeout=timeout_seconds):
            return
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise ConnectionError(
                f"OpenSearch GET {KNOWLEDGE_INDEX} failed: HTTP {exc.code}"
            ) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"OpenSearch is not reachable at {root}") from exc

    body = json.dumps(
        {"settings": {"number_of_shards": 1, "number_of_replicas": 0}}
    ).encode("utf-8")
    put = urllib.request.Request(
        index_url,
        data=body,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(put, timeout=timeout_seconds):
            return
    except urllib.error.HTTPError as exc:
        raise ConnectionError(
            f"OpenSearch PUT {KNOWLEDGE_INDEX} failed: HTTP {exc.code}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"OpenSearch is not reachable at {root}") from exc
