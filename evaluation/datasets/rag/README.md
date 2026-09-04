# RAG retrieval golden set

Each line in `queries.jsonl` is one labelled question.

| Field | Meaning |
| --- | --- |
| `id` | Stable id (`rag-001`, …) |
| `query` | What the Knowledge Agent (or a human) would ask |
| `filters` | Optional FR-042 filters (`doc_type`, `service`, `scenario`) |
| `expected_docs` | Repo-relative paths that **must** appear in top-k |
| `must_not` | Paths that mean the ranker is confused |

This set scores **retrieval**, not RCA accuracy (that is `evaluation/datasets/` golden-rca, Phase 7 / FR-090).

Do not generate rows from live `POST /emit` incidents.
