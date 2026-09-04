---
doc_type: runbook
service: payment
related_services: order
date: 2026-05-20
scenario: db_exhaustion
status: published
severity: high
---

# Runbook — Payment / order DB connection exhaustion

**Scenario id:** `db_exhaustion`  
**Symptom:** `payment` and `order` are both `degraded`. Authorize and place-order fail with pool timeouts (`remaining connections 0`), not a clean 850 ms latency spike on payment alone.

## Immediate checks (read-only)

1. Distinguish from `latency_spike`: here **two** services are degraded and errors mention `connection` / `too many clients`.
2. Payment and order share the checkout Postgres (in production: one cluster, two pools). Count `state = active` vs `max_connections`.
3. Look for a migration or admin session holding a lock (pg_stat_activity).
4. Order depends on payment — if payment pool is empty, order will degrade even if its own pool is healthy. Check both.

## Likely causes

- Leak: request-scoped sessions not returned to the pool after a timeout.
- Burst of checkout retries holding connections across the payment round-trip.
- A one-off `ANALYZE` / long report on the same instance.

## Mitigation (human-approved writes)

- Kill idle-in-transaction backends older than 30s (approver if production).
- Temporarily lower order’s payment-retry concurrency.
- Do not reboot the primary as a first step.

## Escalate

If `remaining connections` stays 0 for 10 minutes, page DBA + payments. Historical RCA: `INC-2026-0511`.
