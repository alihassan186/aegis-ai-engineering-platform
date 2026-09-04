---
doc_type: incident_report
service: order
related_services: payment, inventory
date: 2026-08-14
scenario: dependency_failure
severity: high
incident_id: INC-2026-0814
status: published
---

# INC-2026-0814 — Order timeouts on inventory hop (closed)

**State:** closed  
**Window:** 2026-08-14 18:10–19:55 UTC

## Summary

`order` degraded. Place-order traces showed timeouts calling **inventory**. Inventory status in the catalog stayed `healthy` — the callee was fine; the deadline was wrong. Not `db_exhaustion` (payment pool was healthy).

## Timeline

| UTC | Event |
| --- | --- |
| 18:10 | Checkout 503 / client timeouts. |
| 18:15 | Traces: `order → inventory` span cancelled at 150 ms; inventory p99 ~220 ms. |
| 18:40 | Found deadline change in order 2.3.0 (same morning, not a user deploy). |
| 19:10 | Deadline raised to 400 ms; retries cut to 1 (approved). |
| 19:55 | Error rate normal; closed. |

## Evidence (summary)

- Order status `degraded`; inventory/payment `healthy`.
- Timeout errors on the inventory child span only.
- No `too many clients`; no payment 850 ms-only signature.

## Root cause

Order’s inventory client deadline (150 ms) was below inventory’s real p99 after a catalog sale. Mesh retries + order retries exhausted the parent deadline.

## Fix

Hop deadline 400 ms; retry budget 1. Runbook: `order-dependency-failure.md`.

## Follow-ups

- Per-hop SLOs in the service map.
- Knowledge retrieval should prefer this report when the query says “order timeout inventory,” not the payment latency RCA.
