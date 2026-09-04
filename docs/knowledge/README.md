# Knowledge corpus (RAG)

**Status:** v0.4 Step 3.0 — files only; not indexed yet  
**Owner:** Engineering / on-call

This directory is the **first-class RAG corpus** for AEGIS. Index these files (plus `docs/adr/` and `docs/architecture/`) in OpenSearch. Do **not** index live webhook incidents or simulator `/signals` ticks.

| Kind | Path | `doc_type` |
| --- | --- | --- |
| Runbooks | `runbooks/` | `runbook` |
| Closed historical RCAs | `incidents/` | `incident_report` |
| Service map | `catalog/service-map.md` | `catalog` |

Live `open` incidents stay in **Postgres**. Telemetry stays in the simulator (or a future logs index). This folder is **knowledge**.

## Metadata convention (FR-042)

Every file here starts with YAML frontmatter. Ingest (Step 3.2) must copy these fields onto each chunk.

| Field | Required | Values |
| --- | --- | --- |
| `doc_type` | yes | `runbook` · `incident_report` · `catalog` · `convention` |
| `service` | yes | `user` · `order` · `payment` · `inventory` · `notification` · `platform` |
| `date` | yes | ISO date (`YYYY-MM-DD`) — last review or incident day |
| `scenario` | runbooks + RCAs | FR-083 id (`latency_spike`, `db_exhaustion`, …) |
| `related_services` | no | comma-separated extra services |
| `severity` | RCAs | `low` · `medium` · `high` · `critical` |
| `incident_id` | RCAs | stable id, e.g. `INC-2026-0412` |
| `status` | yes | `published` |

`service` is the **primary** filter. `related_services` is for checkout graphs (order depends on payment).

ADRs and architecture docs outside this folder do not use this frontmatter yet. Retrieval can still key on path (`docs/adr/…`).

## What not to add

- Raw log / metric / span dumps
- Secrets, connection strings, customer PII
- Open incidents copied from `GET /api/v1/incidents`

## Eval

Labelled queries: [`evaluation/datasets/rag/queries.jsonl`](../../evaluation/datasets/rag/queries.jsonl).
