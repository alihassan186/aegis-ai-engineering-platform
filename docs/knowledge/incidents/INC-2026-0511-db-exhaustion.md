---
doc_type: incident_report
service: payment
related_services: order
date: 2026-05-11
scenario: db_exhaustion
severity: high
incident_id: INC-2026-0511
status: published
---

# INC-2026-0511 — Checkout Postgres connection pool exhaustion (closed)

**State:** closed  
**Window:** 2026-05-11 09:18–11:05 UTC

## Summary

`payment` and `order` degraded together. Place-order and authorize returned 503 with `remaining connections 0`. Distinct from INC-2026-0412 (latency-only on payment).

## Timeline

| UTC | Event |
| --- | --- |
| 09:18 | Error budget burn on checkout. |
| 09:22 | Both services `degraded`; pool metrics at cap. |
| 09:35 | pg_stat_activity: checkout API sessions idle-in-transaction after payment timeouts. |
| 10:10 | Killed idle-in-transaction > 30s (approved). |
| 10:25 | Order retry concurrency reduced from 3 to 1. |
| 11:05 | Pools recovered; closed. |

## Evidence (summary)

- `pg_stat_database.numbackends` = `max_connections`.
- Logs: `too many clients` on payment **and** order.
- Order depends on payment — hung payment calls held order’s pool.

## Root cause

Request-scoped DB sessions were not released when the payment HTTP call timed out. Retries opened more sessions. **Leak + retry amplification**, not a small instance size.

## Fix

`asyncio` context manager guaranteed session close; idle-in-transaction timeout 30s on the role. Runbook: `payment-db-exhaustion.md`.

## Follow-ups

- Pool wait histogram as a first-class SLI.
- Do not index this as live webhook JSON; this narrative is the RAG document.
