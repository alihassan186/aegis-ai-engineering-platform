"""Composition root: ``uv run python -m aegis.rag.ingest`` (or ``uv run aegis-ingest``).

Wires Fake/Titan + OpenSearch. Application ingest does not import infrastructure.
Single-file reindex: ``--files docs/knowledge/runbooks/payment-latency-spike.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from aegis.application.rag.allowlist import repository_root
from aegis.application.rag.ingest import ingest_knowledge_corpus
from aegis.config.settings import Settings
from aegis.infrastructure.rag.embedder import build_embedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest the v0.4 RAG allowlist into aegis-knowledge (FR-045).",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="PATH",
        help="Allowlisted repo-relative paths only. Default: all 24 files.",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-embed every selected file even when the content hash matches.",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if not settings.opensearch_url:
        print(
            "AEGIS_OPENSEARCH_URL is required (e.g. http://127.0.0.1:9200).",
            file=sys.stderr,
        )
        return 1
    embedder = build_embedder(settings)
    store = OpenSearchKnowledgeStore(settings.opensearch_url)
    result = ingest_knowledge_corpus(
        embedder=embedder,
        store=store,
        repo_root=repository_root(),
        relative_paths=args.files,
        skip_unchanged=not args.no_skip,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
