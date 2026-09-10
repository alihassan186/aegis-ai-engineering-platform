"""Composition root: ``uv run python -m aegis.rag.eval`` (top_8, queries.jsonl)."""

from __future__ import annotations

import json
import sys

from aegis.application.rag.allowlist import repository_root
from aegis.application.rag.eval import EVAL_TOP_K, score_eval_dataset
from aegis.application.rag.retrieve import RetrieveKnowledge
from aegis.config.settings import Settings
from aegis.infrastructure.rag.embedder import build_embedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore


def main(argv: list[str] | None = None) -> int:
    del argv
    settings = Settings.from_env()
    if not settings.opensearch_url:
        print(
            "AEGIS_OPENSEARCH_URL is required (e.g. http://127.0.0.1:9200).",
            file=sys.stderr,
        )
        return 1
    retrieve = RetrieveKnowledge(
        embedder=build_embedder(settings),
        store=OpenSearchKnowledgeStore(settings.opensearch_url),
    )
    results = score_eval_dataset(retrieve, top_k=EVAL_TOP_K, repo_root=repository_root())
    failed = [row for row in results if not row.passed]
    payload = {
        "top_k": EVAL_TOP_K,
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "cases": [
            {
                "id": row.case_id,
                "passed": row.passed,
                "missing": list(row.missing),
                "must_not_hits": list(row.forbidden_hits),
                "documents": list(row.documents),
            }
            for row in results
        ],
    }
    print(json.dumps(payload, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
